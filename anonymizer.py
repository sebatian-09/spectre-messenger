import random
import struct
import time
import zlib
import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

class TrafficObfuscator:
    """Hide traffic patterns and metadata"""
    
    def __init__(self):
        self.padding_sizes = [128, 256, 512, 1024, 2048]
        self.decoy_patterns = self._generate_decoy_patterns()
        
    def _generate_decoy_patterns(self):
        """Generate fake traffic patterns to confuse analysis"""
        patterns = []
        for _ in range(1000):
            size = random.choice([64, 128, 256, 512, 1024])
            patterns.append(os.urandom(size))
        return patterns
    
    def obfuscate_packet(self, payload):
        """Add noise, padding, and timing randomization"""
        # Add random padding
        pad_size = random.choice(self.padding_sizes)
        padding = os.urandom(pad_size)
        
        # Store padding length in header (4 bytes)
        header = struct.pack('!I', pad_size)
        
        # Compress to reduce predictability
        compressed = zlib.compress(payload + padding)
        
        # Wrap with header
        wrapped = header + compressed
        
        # Add random delay emulation
        time.sleep(random.uniform(0.001, 0.05))
        
        return wrapped
    
    def deobfuscate_packet(self, wrapped_packet):
        """Remove obfuscation"""
        if len(wrapped_packet) < 5:  # 4-byte header + at least 1 byte
            raise ValueError("Packet too short")

        # Extract padding length from header
        header = wrapped_packet[:4]
        pad_size = struct.unpack('!I', header)[0]

        # Validate pad_size against known valid sizes
        if pad_size not in self.padding_sizes and pad_size != 0:
            raise ValueError("Invalid padding size")

        # Decompress
        compressed = wrapped_packet[4:]
        try:
            decompressed = zlib.decompress(compressed)
        except zlib.error as e:
            raise ValueError(f"Decompression failed: {e}")

        # Validate that pad_size doesn't exceed payload
        if pad_size > len(decompressed):
            raise ValueError("Padding size exceeds data length")

        # Remove padding using the stored length
        payload = decompressed[:-pad_size] if pad_size > 0 else decompressed
        
        return payload
    
    def create_decoy_traffic(self):
        """Generate fake messages to confuse traffic analysis"""
        decoy = {
            'type': 'decoy',
            'data': random.choice(self.decoy_patterns),
            'timestamp': time.time(),
            'fake_route': self._generate_fake_route()
        }
        return decoy
    
    def _generate_fake_route(self):
        """Generate fake routing information"""
        hops = random.randint(3, 8)
        route = []
        for _ in range(hops):
            route.append(f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}")
        return route
