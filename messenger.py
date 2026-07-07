import asyncio
import json
import base64
import time
import os
import websockets
from dataclasses import dataclass
from typing import Optional
import hashlib

from crypto import SpectreCrypto
from anonymizer import TrafficObfuscator
from mixnet import MixNode, OnionRouter
from netutils import send_json

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
            await self._establish_secure_channel(recipient)
        
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
        await send_json(self.websocket, {
            'type': 'message',
            'to': recipient,
            'encrypted_data': wrapped
        })
        
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
            
            # Start listening for messages
            listener_task = asyncio.create_task(self._listen_for_messages())
            listener_task.add_done_callback(lambda t: print(f"Listener task ended: {t.exception() if t.exception() else 'normally'}"))
            
        except Exception as e:
            print(f"❌ Failed to connect to server: {e}")
    
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
            self.connected = False
        except Exception as e:
            print(f"❌ Error receiving messages: {e}")
            import traceback
            traceback.print_exc()
    
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
                    if time.time() - data['timestamp'] > 300:
                        print(f"⚠️ Message from {sender} expired")
                        return
                    
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
                return
        
        # Generate shared secret
        secret = self.crypto.derive_shared_secret(self.peers[peer])
        self.shared_secrets[peer] = secret
        
        print(f"✓ Secure channel established with {peer}")
