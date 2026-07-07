import secrets
import struct
import time
import zlib
import os

class TrafficObfuscator:
    """Hide traffic patterns and metadata"""
    
    def __init__(self):
        self.padding_sizes = [128, 256, 512, 1024, 2048]
        self.decoy_patterns = self._generate_decoy_patterns()
        
    def _generate_decoy_patterns(self):
        """Generate fake traffic patterns to confuse analysis"""
        patterns = []
        for _ in range(1000):
            size = secrets.choice([64, 128, 256, 512, 1024])
            patterns.append(os.urandom(size))
        return patterns
    
    def obfuscate_packet(self, payload):
        """Add noise, padding, and timing randomization"""
        # Add random padding
        pad_size = secrets.choice(self.padding_sizes)
        padding = os.urandom(pad_size)
        
        # Store padding length in header (4 bytes)
        header = struct.pack('!I', pad_size)
        
        # Compress to reduce predictability
        compressed = zlib.compress(payload + padding)
        
        # Wrap with header
        wrapped = header + compressed
        
        # Add random delay emulation
        time.sleep(secrets.choice([0.001, 0.005, 0.01, 0.02, 0.05]))
        
        return wrapped
    
    def deobfuscate_packet(self, wrapped_packet):
        """Remove obfuscation"""
        # Extract padding length from header
        header = wrapped_packet[:4]
        pad_size = struct.unpack('!I', header)[0]
        
        # Decompress
        compressed = wrapped_packet[4:]
        decompressed = zlib.decompress(compressed)
        
        # Remove padding using the stored length
        if pad_size > len(decompressed):
            raise ValueError("Invalid padding length")
        payload = decompressed[:-pad_size] if pad_size > 0 else decompressed
        
        return payload
    
    def create_decoy_traffic(self):
        """Generate fake messages to confuse traffic analysis"""
        decoy = {
            'type': 'decoy',
            'data': secrets.choice(self.decoy_patterns),
            'timestamp': time.time(),
            'fake_route': self._generate_fake_route()
        }
        return decoy
    
    def _generate_fake_route(self):
        """Generate fake routing information"""
        hops = secrets.randbelow(6) + 3
        route = []
        for _ in range(hops):
            route.append(
                ".".join(str(secrets.randbelow(255) + 1) for _ in range(4))
            )
        return route
