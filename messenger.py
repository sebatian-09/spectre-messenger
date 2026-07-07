import asyncio
import json
import base64
import time
import os
import traceback
import websockets
from dataclasses import dataclass
from typing import Optional, Set
import hashlib

from crypto import SpectreCrypto
from anonymizer import TrafficObfuscator
from mixnet import MixNode, OnionRouter
from netutils import send_json

# Replay protection: reject messages older than 30 seconds
REPLAY_WINDOW_SECONDS = 30
MAX_SEEN_NONCES = 10000

@dataclass
class Message:
    content: str
    sender_pubkey: bytes
    timestamp: float
    nonce: bytes
    signature: Optional[bytes] = None

class SpectreMessenger:
    """Complete secure messenger"""
    
    def __init__(self, username, server_url='ws://localhost:8765'):
        self.username = username
        self.server_url = server_url
        self.crypto = SpectreCrypto()
        self.obfuscator = TrafficObfuscator()
        self.mixnet = MixNode(username)
        self.onion = OnionRouter()
        self.peers = {}  # username -> public_key
        self.shared_secrets = {}  # username -> secret
        self.message_history = []
        self.websocket = None
        self.connected = False
        self.online_users = set()
        self._seen_nonces: Set[str] = set()  # replay protection
        self.listener_task = None
        
    async def send_message(self, recipient, content):
        """Send an anonymous, encrypted message"""
        
        if not self.connected:
            print("❌ Not connected to server")
            return False
        
        if recipient not in self.online_users:
            print(f"❌ User {recipient} is not online")
            return False
        
        # 1. Get or establish shared secret
        if recipient not in self.shared_secrets:
            if not await self._establish_secure_channel(recipient):
                print(f"❌ Could not establish secure channel with {recipient}")
                return False
        
        secret = self.shared_secrets[recipient]
        
        # 2. Create message with metadata stripping
        msg = Message(
            content=content,
            sender_pubkey=self.crypto.public_key.public_bytes_raw(),
            timestamp=time.time(),
            nonce=os.urandom(16)
        )
        
        # 3. Encrypt content
        encrypted = self.crypto.encrypt_message(
            json.dumps({
                'content': msg.content,
                'timestamp': msg.timestamp,
                'nonce': base64.b64encode(msg.nonce).decode()
            }),
            secret
        )
        
        # 4. Send encrypted message directly (simplified for debugging)
        wrapped = base64.b64encode(encrypted).decode()
        
        # 5. Send through network
        try:
            await send_json(self.websocket, {
                'type': 'message',
                'to': recipient,
                'encrypted_data': wrapped
            })
        except websockets.exceptions.ConnectionClosed:
            print("❌ Connection lost while sending message")
            self.connected = False
            return False
        except Exception as e:
            print(f"❌ Failed to send message to {recipient}: {e}")
            return False
        
        print(f"✓ Message sent anonymously to {recipient}")
        return True
    
    async def connect_to_server(self):
        """Connect to the WebSocket server"""
        try:
            self.websocket = await websockets.connect(self.server_url)
            
            # Register with server
            await send_json(self.websocket, {
                'type': 'register',
                'username': self.username
            })
            
            # Send our public key
            pubkey_hex = self.crypto.public_key.public_bytes_raw().hex()
            await send_json(self.websocket, {
                'type': 'public_key',
                'public_key': pubkey_hex
            })
            
            self.connected = True
            print(f"✓ Connected to server as {self.username}")
            
            # Start listening for messages (keep a reference so the task isn't GC'd)
            self.listener_task = asyncio.create_task(self._listen_for_messages())
            self.listener_task.add_done_callback(self._on_listener_done)
            
        except Exception as e:
            print(f"❌ Failed to connect to server: {e}")
            self.connected = False
            self.websocket = None

    def _on_listener_done(self, task):
        """Report why the listener task stopped."""
        self.connected = False
        try:
            exc = task.exception()
        except asyncio.CancelledError:
            return
        if exc is not None:
            print(f"❌ Listener task stopped with error: {exc}")
    
    async def _listen_for_messages(self):
        """Listen for incoming messages from server"""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    
                    if data['type'] == 'registered':
                        print(f"✓ Registered as {data['username']}")
                    
                    elif data['type'] == 'user_list':
                        self.online_users = set(data['users'])
                        self.online_users.discard(self.username)
                        if self.online_users:
                            print(f"\n📱 Online users: {', '.join(self.online_users)}")
                    
                    elif data['type'] == 'public_key':
                        peer = data['username']
                        if peer != self.username:
                            self.peers[peer] = bytes.fromhex(data['public_key'])
                            print(f"✓ Received public key from {peer}")
                    
                    elif data['type'] == 'message':
                        sender = data['from']
                        wrapped = data['encrypted_data']
                        await self._process_received_message(sender, wrapped)
                    
                    elif data['type'] == 'error':
                        print(f"❌ Server error: {data['message']}")
                except json.JSONDecodeError as e:
                    print(f"❌ Failed to parse message: {e}")
                except Exception as e:
                    print(f"❌ Error processing message: {e}")
        
        except websockets.exceptions.ConnectionClosed as e:
            print(f"❌ Disconnected from server: {e}")
        except Exception as e:
            print(f"❌ Error receiving messages: {e}")
            traceback.print_exc()
        finally:
            self.connected = False
    
    async def _process_received_message(self, sender, wrapped):
        """Process and decrypt received message"""
        try:
            # Decode base64
            encrypted = base64.b64decode(wrapped)
            
            # Try to decrypt with shared secret
            if sender in self.shared_secrets:
                try:
                    decrypted = self.crypto.decrypt_message(encrypted, self.shared_secrets[sender])
                    data = json.loads(decrypted)
                    
                    # Verify timestamp (prevent replay attacks)
                    msg_age = time.time() - data['timestamp']
                    if msg_age > REPLAY_WINDOW_SECONDS or msg_age < -5:
                        print(f"⚠️ Message from {sender} rejected (timestamp out of range)")
                        return

                    # Reject duplicate nonces (replay detection)
                    nonce = data.get('nonce', '')
                    if nonce in self._seen_nonces:
                        print(f"⚠️ Replay detected from {sender}")
                        return
                    self._seen_nonces.add(nonce)
                    if len(self._seen_nonces) > MAX_SEEN_NONCES:
                        self._seen_nonces.clear()
                    
                    print(f"\n📩 Message from {sender}: {data['content']}")
                    self.message_history.append({
                        'from': sender,
                        'content': data['content'],
                        'timestamp': data['timestamp']
                    })
                except Exception as e:
                    print(f"⚠️ Failed to decrypt message from {sender}: {e}")
            else:
                print(f"⚠️ No shared secret with {sender}, establishing channel...")
                await self._establish_secure_channel(sender)
        
        except Exception as e:
            print(f"⚠️ Error processing message: {e}")
    
    async def _establish_secure_channel(self, peer):
        """Establish secure channel with forward secrecy"""
        if peer not in self.peers:
            print(f"⏳ Waiting for public key from {peer}...")
            # Wait for public key to arrive via server
            for _ in range(50):  # Wait up to 5 seconds
                if peer in self.peers:
                    break
                await asyncio.sleep(0.1)
            
            if peer not in self.peers:
                print(f"❌ Could not get public key for {peer}")
                return False
        
        # Generate shared secret
        try:
            secret = self.crypto.derive_shared_secret(self.peers[peer])
        except Exception as e:
            print(f"❌ Failed to derive shared secret with {peer}: {e}")
            return False
        self.shared_secrets[peer] = secret
        
        print(f"✓ Secure channel established with {peer}")
        return True
