import os
import hashlib
import hmac
import time
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.backends import default_backend
import blake3

class SpectreCrypto:
    """Military-grade encryption with forward secrecy"""
    
    def __init__(self):
        self.private_key = x25519.X25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()
        
    def derive_shared_secret(self, peer_public_key_bytes):
        """X25519 ECDH + BLAKE3 KDF"""
        peer_key = x25519.X25519PublicKey.from_public_bytes(peer_public_key_bytes)
        shared_secret = self.private_key.exchange(peer_key)
        
        # Double KDF for extra safety
        kdf = HKDF(
            algorithm=hashes.BLAKE2b(64),
            length=32,
            salt=b'spectre_salt_v1',
            info=b'handshake',
            backend=default_backend()
        )
        return kdf.derive(shared_secret)
    
    @staticmethod
    def _derive_encryption_key(shared_secret):
        """Derive the symmetric ChaCha20-Poly1305 key from a shared secret"""
        return blake3.blake3(shared_secret + b'encrypt').digest(32)
    
    def encrypt_message(self, message, shared_secret):
        """ChaCha20-Poly1305 with random nonce"""
        key = self._derive_encryption_key(shared_secret)
        nonce = os.urandom(12)  # ChaCha20 uses 12-byte nonce
        cipher = ChaCha20Poly1305(key)
        ciphertext = cipher.encrypt(nonce, message.encode(), b'')
        return nonce + ciphertext
    
    def decrypt_message(self, encrypted_data, shared_secret):
        """Decrypt with authentication"""
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        key = self._derive_encryption_key(shared_secret)
        cipher = ChaCha20Poly1305(key)
        return cipher.decrypt(nonce, ciphertext, b'').decode()
