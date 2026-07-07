import asyncio
import json
import base64
import binascii
import logging
import random
import time

logger = logging.getLogger(__name__)

class MixNode:
    """Mix network node that batches and delays messages"""
    
    def __init__(self, node_id):
        self.node_id = node_id
        self.message_queue = []
        self.batch_size = random.randint(5, 20)
        self.delay = random.uniform(0.5, 3.0)
        self.output_queue = []
        
    async def receive_message(self, message):
        """Receive encrypted message"""
        self.message_queue.append({
            'message': message,
            'received': time.time(),
            'source': None  # We don't track source
        })
        
        if len(self.message_queue) >= self.batch_size:
            await self.process_batch()
    
    async def process_batch(self):
        """Process messages in batch (mix)"""
        await asyncio.sleep(self.delay)  # Random delay
        
        # Shuffle messages
        random.shuffle(self.message_queue)
        
        # Forward to next hop or destination
        for msg in self.message_queue:
            # Each message gets different routing
            result = await self.forward_message(msg['message'])
            self.output_queue.append(result)
        
        self.message_queue.clear()
    
    async def forward_message(self, message):
        """Forward to next node (random routing)"""
        # In real implementation, use onion routing
        # For demo, we'll just pass through
        return message
    
    async def get_messages(self):
        """Get processed messages from output queue"""
        messages = self.output_queue.copy()
        self.output_queue.clear()
        return messages

class OnionRouter:
    """Onion routing for sender anonymity"""
    
    def __init__(self):
        self.nodes = self._discover_nodes()
        self.circuit = []
        
    def _discover_nodes(self):
        """Discover mix nodes (in real impl, use DHT)"""
        return [f"node_{i}" for i in range(10)]
    
    def create_circuit(self, length=3):
        """Create random circuit through mix network"""
        self.circuit = random.sample(self.nodes, length)
        return self.circuit
    
    def wrap_message(self, message, circuit):
        """Wrap message in onion layers"""
        wrapped = message
        for node in reversed(circuit):
            # Each layer is encrypted with node's key
            layer = {
                'next_hop': node,
                'payload': wrapped,
                'timestamp': time.time()
            }
            # Encrypt layer (simplified)
            wrapped = base64.b64encode(json.dumps(layer).encode()).decode()
        return wrapped
    
    def unwrap_message(self, wrapped_message):
        """Unwrap onion layers"""
        # In real implementation, each node decrypts its layer
        # For demo, we'll just decode
        try:
            data = json.loads(base64.b64decode(wrapped_message))
            return data['payload']
        except (json.JSONDecodeError, binascii.Error, ValueError, KeyError, TypeError) as e:
            # Not an onion-wrapped layer (e.g. already-unwrapped payload); pass through.
            logger.debug(f"unwrap_message: treating input as unwrapped payload ({e})")
            return wrapped_message
