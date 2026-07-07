import os
import pytest
from crypto import SpectreCrypto


class TestSpectreCryptoInit:
    def test_generates_private_and_public_key(self):
        crypto = SpectreCrypto()
        assert crypto.private_key is not None
        assert crypto.public_key is not None

    def test_different_instances_have_different_keys(self):
        c1 = SpectreCrypto()
        c2 = SpectreCrypto()
        assert c1.public_key.public_bytes_raw() != c2.public_key.public_bytes_raw()

    def test_public_key_is_32_bytes(self):
        crypto = SpectreCrypto()
        assert len(crypto.public_key.public_bytes_raw()) == 32


class TestDeriveSharedSecret:
    def test_shared_secret_is_32_bytes(self):
        alice = SpectreCrypto()
        bob = SpectreCrypto()
        secret = alice.derive_shared_secret(bob.public_key.public_bytes_raw())
        assert len(secret) == 32

    def test_both_sides_derive_same_secret(self):
        alice = SpectreCrypto()
        bob = SpectreCrypto()
        secret_a = alice.derive_shared_secret(bob.public_key.public_bytes_raw())
        secret_b = bob.derive_shared_secret(alice.public_key.public_bytes_raw())
        assert secret_a == secret_b

    def test_different_peers_yield_different_secrets(self):
        alice = SpectreCrypto()
        bob = SpectreCrypto()
        charlie = SpectreCrypto()
        secret_ab = alice.derive_shared_secret(bob.public_key.public_bytes_raw())
        secret_ac = alice.derive_shared_secret(charlie.public_key.public_bytes_raw())
        assert secret_ab != secret_ac

    def test_rejects_invalid_public_key_length(self):
        crypto = SpectreCrypto()
        with pytest.raises(Exception):
            crypto.derive_shared_secret(b'\x00' * 16)


class TestEncryptDecrypt:
    def setup_method(self):
        self.alice = SpectreCrypto()
        self.bob = SpectreCrypto()
        self.shared_secret = self.alice.derive_shared_secret(
            self.bob.public_key.public_bytes_raw()
        )

    def test_encrypt_returns_bytes(self):
        ct = self.alice.encrypt_message("hello", self.shared_secret)
        assert isinstance(ct, bytes)

    def test_ciphertext_starts_with_12_byte_nonce(self):
        ct = self.alice.encrypt_message("test", self.shared_secret)
        assert len(ct) > 12

    def test_roundtrip_short_message(self):
        msg = "hello"
        ct = self.alice.encrypt_message(msg, self.shared_secret)
        pt = self.bob.decrypt_message(ct, self.shared_secret)
        assert pt == msg

    def test_roundtrip_empty_message(self):
        msg = ""
        ct = self.alice.encrypt_message(msg, self.shared_secret)
        pt = self.bob.decrypt_message(ct, self.shared_secret)
        assert pt == msg

    def test_roundtrip_unicode_message(self):
        msg = "こんにちは 🌍"
        ct = self.alice.encrypt_message(msg, self.shared_secret)
        pt = self.bob.decrypt_message(ct, self.shared_secret)
        assert pt == msg

    def test_roundtrip_long_message(self):
        msg = "A" * 10000
        ct = self.alice.encrypt_message(msg, self.shared_secret)
        pt = self.bob.decrypt_message(ct, self.shared_secret)
        assert pt == msg

    def test_different_nonce_each_encryption(self):
        ct1 = self.alice.encrypt_message("hello", self.shared_secret)
        ct2 = self.alice.encrypt_message("hello", self.shared_secret)
        assert ct1[:12] != ct2[:12]

    def test_ciphertext_differs_for_same_plaintext(self):
        ct1 = self.alice.encrypt_message("hello", self.shared_secret)
        ct2 = self.alice.encrypt_message("hello", self.shared_secret)
        assert ct1 != ct2

    def test_wrong_secret_fails_to_decrypt(self):
        ct = self.alice.encrypt_message("secret", self.shared_secret)
        wrong_secret = os.urandom(32)
        with pytest.raises(Exception):
            self.bob.decrypt_message(ct, wrong_secret)

    def test_tampered_ciphertext_fails(self):
        ct = self.alice.encrypt_message("test", self.shared_secret)
        tampered = ct[:12] + bytes([ct[12] ^ 0xFF]) + ct[13:]
        with pytest.raises(Exception):
            self.bob.decrypt_message(tampered, self.shared_secret)

    def test_truncated_ciphertext_fails(self):
        ct = self.alice.encrypt_message("test", self.shared_secret)
        with pytest.raises(Exception):
            self.bob.decrypt_message(ct[:15], self.shared_secret)

    def test_either_party_can_decrypt(self):
        secret_b = self.bob.derive_shared_secret(
            self.alice.public_key.public_bytes_raw()
        )
        ct = self.alice.encrypt_message("bidirectional", self.shared_secret)
        pt = self.bob.decrypt_message(ct, secret_b)
        assert pt == "bidirectional"
