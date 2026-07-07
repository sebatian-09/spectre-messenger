import asyncio
import websockets
import json
import logging
from typing import Dict, Set

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SpectreServer:
    """WebSocket server for peer-to-peer encrypted messaging"""
    
    def __init__(self, host='localhost', port=8765):
        self.host = host
        self.port = port
        self.clients: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.public_keys: Dict[str, str] = {}  # username -> public_key (hex)
        
    async def register(self, websocket, username):
        """Register a new client"""
        if username in self.clients:
            logger.warning(f"Username {username} already taken")
            await websocket.send(json.dumps({
                'type': 'error',
                'message': 'Username already taken'
            }))
            return False
        
        self.clients[username] = websocket
        logger.info(f"User {username} connected")
        await websocket.send(json.dumps({
            'type': 'registered',
            'username': username
        }))
        
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
        user_list = list(self.clients.keys())
        message = json.dumps({
            'type': 'user_list',
            'users': user_list
        })
        
        # Send to all connected clients (make a copy to avoid modification during iteration)
        clients_copy = list(self.clients.values())
        for client in clients_copy:
            try:
                await client.send(message)
            except:
                pass
    
    async def handle_public_key(self, username, public_key_hex):
        """Store and broadcast public key"""
        self.public_keys[username] = public_key_hex
        logger.info(f"Public key registered for {username}")
        
        # Broadcast to all clients
        message = json.dumps({
            'type': 'public_key',
            'username': username,
            'public_key': public_key_hex
        })
        
        for client in self.clients.values():
            try:
                await client.send(message)
            except:
                pass
    
    async def handle_message(self, sender, recipient, encrypted_message):
        """Route encrypted message to recipient"""
        if recipient not in self.clients:
            logger.warning(f"Recipient {recipient} not found")
            return False
        
        recipient_ws = self.clients[recipient]
        message = json.dumps({
            'type': 'message',
            'from': sender,
            'encrypted_data': encrypted_message
        })
        
        try:
            await recipient_ws.send(message)
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
                    data = json.loads(message)
                    logger.info(f"Received message type: {data.get('type')}")
                    
                    if data['type'] == 'register':
                        username = data['username']
                        logger.info(f"Attempting to register user: {username}")
                        if await self.register(websocket, username):
                            # Send existing public keys to new user
                            for user, pubkey in self.public_keys.items():
                                await websocket.send(json.dumps({
                                    'type': 'public_key',
                                    'username': user,
                                    'public_key': pubkey
                                }))
                    
                    elif data['type'] == 'public_key':
                        await self.handle_public_key(username, data['public_key'])
                    
                    elif data['type'] == 'message':
                        await self.handle_message(
                            username,
                            data['to'],
                            data['encrypted_data']
                        )
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse message: {e}")
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
        
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Connection closed for user {username}")
        except Exception as e:
            logger.error(f"Error in handle_client: {e}")
        finally:
            if username:
                await self.unregister(username)
    
    async def start(self):
        """Start the server"""
        logger.info(f"Starting Spectre server on {self.host}:{self.port}")
        async with websockets.serve(self.handle_client, self.host, self.port):
            await asyncio.Future()  # Run forever

async def main():
    server = SpectreServer(host='0.0.0.0', port=8765)
    await server.start()

if __name__ == "__main__":
    asyncio.run(main())
