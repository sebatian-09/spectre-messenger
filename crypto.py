import os
import hashlib
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives import serialization
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
        
        local_public_key_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        salt = hashlib.sha256(
            b"|".join(sorted([local_public_key_bytes, peer_public_key_bytes]))
        ).digest()

        kdf = HKDF(
            algorithm=hashes.BLAKE2b(64),
            length=32,
            salt=salt,
            info=b'handshake',
        )
        return kdf.derive(shared_secret)
    
    def encrypt_message(self, message, shared_secret):
        """ChaCha20-Poly1305 with random nonce"""
        key = blake3.blake3(shared_secret + b'encrypt').digest(32)
        nonce = os.urandom(12)  # ChaCha20 uses 12-byte nonce
        cipher = ChaCha20Poly1305(key)
        ciphertext = cipher.encrypt(nonce, message.encode(), b'')
        return nonce + ciphertext
    
    def decrypt_message(self, encrypted_data, shared_secret):
        """Decrypt with authentication"""
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        key = blake3.blake3(shared_secret + b'encrypt').digest(32)
        cipher = ChaCha20Poly1305(key)
        return cipher.decrypt(nonce, ciphertext, b'').decode()
