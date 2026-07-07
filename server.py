import asyncio
import re
import websockets
import json
import logging
import time
from collections import defaultdict
from typing import Dict, Set
from aiohttp import web

from netutils import send_json, broadcast_json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Security constants
MAX_USERNAME_LENGTH = 32
USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
MAX_MESSAGE_SIZE = 65536  # 64 KB max message payload
MAX_CLIENTS = 1000
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_MESSAGES = 60  # messages per window per user

class SpectreServer:
    """WebSocket server for peer-to-peer encrypted messaging"""
    
    def __init__(self, host='localhost', port=8765):
        self.host = host
        self.port = port
        self.clients: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.public_keys: Dict[str, str] = {}  # username -> public_key (hex)
        self._message_counts: Dict[str, list] = defaultdict(list)  # rate limiting

    def _is_valid_username(self, username: str) -> bool:
        """Validate username format to prevent injection attacks"""
        if not username or len(username) > MAX_USERNAME_LENGTH:
            return False
        return bool(USERNAME_PATTERN.match(username))

    def _check_rate_limit(self, username: str) -> bool:
        """Return True if user is within rate limit, False if exceeded"""
        now = time.time()
        timestamps = self._message_counts[username]
        # Prune old entries
        self._message_counts[username] = [
            t for t in timestamps if now - t < RATE_LIMIT_WINDOW
        ]
        if len(self._message_counts[username]) >= RATE_LIMIT_MAX_MESSAGES:
            return False
        self._message_counts[username].append(now)
        return True
        
    async def register(self, websocket, username):
        """Register a new client"""
        if not self._is_valid_username(username):
            await websocket.send(json.dumps({
                'type': 'error',
                'message': 'Invalid username. Use 1-32 alphanumeric characters, hyphens, or underscores.'
            }))
            return False

        if len(self.clients) >= MAX_CLIENTS:
            await websocket.send(json.dumps({
                'type': 'error',
                'message': 'Server is at maximum capacity'
            }))
            return False

        if username in self.clients:
            logger.warning(f"Username {username} already taken")
            await send_json(websocket, {
                'type': 'error',
                'message': 'Username already taken'
            })
            return False
        
        self.clients[username] = websocket
        logger.info(f"User {username} connected")
        await send_json(websocket, {
            'type': 'registered',
            'username': username
        })
        
        # Broadcast user list to all clients
        await self.broadcast_user_list()
        return True
    
    async def unregister(self, username):
        """Unregister a client"""
        if username in self.clients:
            del self.clients[username]
            if username in self.public_keys:
                del self.public_keys[username]
            logger.info(f"User {username} disconnected")
            # Don't broadcast during shutdown to avoid race conditions
            if len(self.clients) > 0:
                await self.broadcast_user_list()
    
    async def broadcast_user_list(self):
        """Send updated user list to all clients"""
        await broadcast_json(self.clients.values(), {
            'type': 'user_list',
            'users': list(self.clients.keys())
        })
    
    async def handle_public_key(self, username, public_key_hex):
        """Store and broadcast public key"""
        self.public_keys[username] = public_key_hex
        logger.info(f"Public key registered for {username}")
        
        # Broadcast to all clients
        await broadcast_json(self.clients.values(), {
            'type': 'public_key',
            'username': username,
            'public_key': public_key_hex
        })
    
    async def handle_message(self, sender, recipient, encrypted_message):
        """Route encrypted message to recipient"""
        if recipient not in self.clients:
            logger.warning(f"Recipient {recipient} not found")
            return False
        
        recipient_ws = self.clients[recipient]
        try:
            await send_json(recipient_ws, {
                'type': 'message',
                'from': sender,
                'encrypted_data': encrypted_message
            })
            logger.info(f"Message routed from {sender} to {recipient}")
            return True
        except:
            logger.error(f"Failed to send message to {recipient}")
            return False
    
    async def handle_client(self, websocket):
        """Handle client connection"""
        username = None
        
        try:
            # Wait for registration
            async for message in websocket:
                try:
                    # Enforce message size limit
                    if len(message) > MAX_MESSAGE_SIZE:
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': 'Message too large'
                        }))
                        continue

                    data = json.loads(message)
                    msg_type = data.get('type')
                    
                    if msg_type == 'register':
                        username = data.get('username', '')
                        if await self.register(websocket, username):
                            # Send existing public keys to new user
                            for user, pubkey in self.public_keys.items():
                                await send_json(websocket, {
                                    'type': 'public_key',
                                    'username': user,
                                    'public_key': pubkey
                                })
                    
                    elif msg_type == 'public_key':
                        if username is None:
                            continue
                        public_key = data.get('public_key', '')
                        if not public_key or len(public_key) != 64:
                            continue  # X25519 public key is 32 bytes = 64 hex chars
                        await self.handle_public_key(username, public_key)
                    
                    elif msg_type == 'message':
                        if username is None:
                            continue
                        if not self._check_rate_limit(username):
                            await websocket.send(json.dumps({
                                'type': 'error',
                                'message': 'Rate limit exceeded. Slow down.'
                            }))
                            continue
                        recipient = data.get('to', '')
                        encrypted_data = data.get('encrypted_data', '')
                        if not recipient or not encrypted_data:
                            continue
                        if len(encrypted_data) > MAX_MESSAGE_SIZE:
                            continue
                        await self.handle_message(
                            username,
                            recipient,
                            encrypted_data
                        )
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from {username or 'unknown'}")
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
        
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Connection closed for user {username}")
        except Exception as e:
            logger.error(f"Error in handle_client: {e}")
        finally:
            if username:
                await self.unregister(username)
    
    async def health_check(self, request):
        """Health check endpoint for Render"""
        return web.Response(text="OK", status=200)
    
    async def start(self):
        """Start the server"""
        logger.info(f"Starting Spectre server on {self.host}:{self.port}")
        
        # Create HTTP app for health checks
        app = web.Application()
        app.router.add_get('/', self.health_check)
        app.router.add_head('/', self.health_check)
        
        # Start HTTP server
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        
        # Start WebSocket server on same port
        async with websockets.serve(self.handle_client, self.host, self.port):
            await asyncio.Future()  # Run forever

async def main():
    server = SpectreServer(host='0.0.0.0', port=8765)
    await server.start()

if __name__ == "__main__":
    asyncio.run(main())
