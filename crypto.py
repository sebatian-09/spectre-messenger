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
        if len(peer_public_key_bytes) != 32:
            raise ValueError("Invalid public key length")
        peer_key = x25519.X25519PublicKey.from_public_bytes(peer_public_key_bytes)
        shared_secret = self.private_key.exchange(peer_key)
        
        # Derive the HKDF salt deterministically from both public keys so that
        # both peers compute the same salt (and therefore the same key). Sorting
        # makes it order-independent regardless of who initiates.
        own_public_bytes = self.public_key.public_bytes_raw()
        salt = b''.join(sorted([own_public_bytes, peer_public_key_bytes]))
        
        kdf = HKDF(
            algorithm=hashes.BLAKE2b(64),
            length=32,
            salt=salt,
            info=b'spectre-handshake-v2',
            backend=default_backend()
        )
        return kdf.derive(shared_secret)
    
    def encrypt_message(self, message, shared_secret):
        """ChaCha20-Poly1305 with random nonce"""
        if not isinstance(shared_secret, bytes) or len(shared_secret) != 32:
            raise ValueError("Invalid shared secret")
        key = blake3.blake3(shared_secret + b'encrypt').digest(length=32)
        nonce = os.urandom(12)
        cipher = ChaCha20Poly1305(key)
        ciphertext = cipher.encrypt(nonce, message.encode(), b'')
        return nonce + ciphertext
    
    def decrypt_message(self, encrypted_data, shared_secret):
        """Decrypt with authentication"""
        if not isinstance(shared_secret, bytes) or len(shared_secret) != 32:
            raise ValueError("Invalid shared secret")
        if len(encrypted_data) < 13:  # 12-byte nonce + at least 1 byte
            raise ValueError("Ciphertext too short")
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        key = blake3.blake3(shared_secret + b'encrypt').digest(length=32)
        cipher = ChaCha20Poly1305(key)
        return cipher.decrypt(nonce, ciphertext, b'').decode()
