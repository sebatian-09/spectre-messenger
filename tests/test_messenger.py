import asyncio
import json
import base64
import time
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import fields

from messenger import Message, SpectreMessenger


class FakeWebSocket:
    """Mock websocket that supports async iteration and send."""

    def __init__(self, messages=None):
        self.messages = messages or []
        self.sent = []

    def __aiter__(self):
        return self._iter()

    async def _iter(self):
        for msg in self.messages:
            yield msg

    async def send(self, data):
        self.sent.append(data)

    async def close(self):
        pass


class TestMessageDataclass:
    def test_message_fields(self):
        field_names = {f.name for f in fields(Message)}
        assert field_names == {'content', 'sender_pubkey', 'timestamp', 'nonce', 'signature'}

    def test_message_creation(self):
        msg = Message(
            content="hello",
            sender_pubkey=b'\x01' * 32,
            timestamp=1000.0,
            nonce=b'\x02' * 16,
        )
        assert msg.content == "hello"
        assert msg.sender_pubkey == b'\x01' * 32
        assert msg.timestamp == 1000.0
        assert msg.nonce == b'\x02' * 16
        assert msg.signature is None

    def test_message_with_signature(self):
        msg = Message(
            content="signed",
            sender_pubkey=b'\x01' * 32,
            timestamp=1000.0,
            nonce=b'\x02' * 16,
            signature=b'\x03' * 64
        )
        assert msg.signature == b'\x03' * 64


class TestSpectreMessengerInit:
    def test_defaults(self):
        m = SpectreMessenger("alice")
        assert m.username == "alice"
        assert m.server_url == 'ws://localhost:8765'
        assert m.peers == {}
        assert m.shared_secrets == {}
        assert m.message_history == []
        assert m.websocket is None
        assert m.connected is False
        assert m.online_users == set()

    def test_custom_server_url(self):
        m = SpectreMessenger("bob", server_url="ws://example.com:9000")
        assert m.server_url == "ws://example.com:9000"

    def test_has_crypto_instance(self):
        m = SpectreMessenger("alice")
        assert m.crypto is not None
        assert m.crypto.public_key is not None

    def test_has_obfuscator(self):
        m = SpectreMessenger("alice")
        assert m.obfuscator is not None

    def test_has_mixnet_and_onion(self):
        m = SpectreMessenger("alice")
        assert m.mixnet is not None
        assert m.onion is not None


class TestSendMessageGuards:
    @pytest.mark.asyncio
    async def test_send_when_not_connected(self):
        m = SpectreMessenger("alice")
        m.connected = False
        result = await m.send_message("bob", "hello")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_to_offline_user(self):
        m = SpectreMessenger("alice")
        m.connected = True
        m.online_users = {"charlie"}
        result = await m.send_message("bob", "hello")
        assert result is False


class TestSendMessageFlow:
    @pytest.mark.asyncio
    async def test_send_message_with_existing_secret(self):
        m = SpectreMessenger("alice")
        m.connected = True
        m.online_users = {"bob"}
        # Pre-populate shared secret
        m.shared_secrets["bob"] = os.urandom(32)
        m.websocket = AsyncMock()

        result = await m.send_message("bob", "hello bob")
        assert result is True
        m.websocket.send.assert_called_once()

        # Verify sent message structure
        sent = json.loads(m.websocket.send.call_args[0][0])
        assert sent['type'] == 'message'
        assert sent['to'] == 'bob'
        assert 'encrypted_data' in sent

    @pytest.mark.asyncio
    async def test_sent_message_is_encrypted(self):
        m = SpectreMessenger("alice")
        m.connected = True
        m.online_users = {"bob"}
        m.shared_secrets["bob"] = os.urandom(32)
        m.websocket = AsyncMock()

        await m.send_message("bob", "plaintext secret")
        sent = json.loads(m.websocket.send.call_args[0][0])
        # The encrypted_data should be base64 encoded
        encrypted_bytes = base64.b64decode(sent['encrypted_data'])
        # Should not contain plaintext
        assert b"plaintext secret" not in encrypted_bytes


class TestProcessReceivedMessage:
    @pytest.mark.asyncio
    async def test_decrypt_valid_message(self):
        alice = SpectreMessenger("alice")
        bob = SpectreMessenger("bob")

        # Sync session salts so both sides derive the same shared secret
        bob.crypto._session_salt = alice.crypto._session_salt

        alice_pub = alice.crypto.public_key.public_bytes_raw()
        bob_pub = bob.crypto.public_key.public_bytes_raw()

        secret_alice = alice.crypto.derive_shared_secret(bob_pub)
        secret_bob = bob.crypto.derive_shared_secret(alice_pub)

        bob.shared_secrets["alice"] = secret_bob

        # Alice encrypts a message
        msg_data = json.dumps({
            'content': "hello bob!",
            'timestamp': time.time(),
            'nonce': base64.b64encode(os.urandom(16)).decode()
        })
        encrypted = alice.crypto.encrypt_message(msg_data, secret_alice)
        wrapped = base64.b64encode(encrypted).decode()

        # Bob processes it
        await bob._process_received_message("alice", wrapped)
        assert len(bob.message_history) == 1
        assert bob.message_history[0]['content'] == "hello bob!"
        assert bob.message_history[0]['from'] == "alice"

    @pytest.mark.asyncio
    async def test_expired_message_not_stored(self):
        alice = SpectreMessenger("alice")
        bob = SpectreMessenger("bob")

        bob.crypto._session_salt = alice.crypto._session_salt

        alice_pub = alice.crypto.public_key.public_bytes_raw()
        bob_pub = bob.crypto.public_key.public_bytes_raw()

        secret_alice = alice.crypto.derive_shared_secret(bob_pub)
        secret_bob = bob.crypto.derive_shared_secret(alice_pub)

        bob.shared_secrets["alice"] = secret_bob

        # Message with old timestamp (> REPLAY_WINDOW_SECONDS)
        msg_data = json.dumps({
            'content': "old message",
            'timestamp': time.time() - 400,
            'nonce': base64.b64encode(os.urandom(16)).decode()
        })
        encrypted = alice.crypto.encrypt_message(msg_data, secret_alice)
        wrapped = base64.b64encode(encrypted).decode()

        await bob._process_received_message("alice", wrapped)
        assert len(bob.message_history) == 0

    @pytest.mark.asyncio
    async def test_no_shared_secret_triggers_channel_establishment(self):
        bob = SpectreMessenger("bob")
        bob.shared_secrets = {}  # No secret for alice
        bob.peers = {}

        # Should not crash, just print warning
        wrapped = base64.b64encode(b"garbage").decode()
        await bob._process_received_message("alice", wrapped)
        # No history since we couldn't decrypt
        assert len(bob.message_history) == 0


class TestConnectToServer:
    @pytest.mark.asyncio
    async def test_connect_success(self):
        m = SpectreMessenger("alice")
        fake_ws = FakeWebSocket([])

        async def fake_connect(*args, **kwargs):
            return fake_ws

        with patch('messenger.websockets.connect', side_effect=fake_connect):
            await m.connect_to_server()

        # Verify registration and public key were sent
        assert m.websocket == fake_ws
        assert len(fake_ws.sent) == 2
        reg_msg = json.loads(fake_ws.sent[0])
        assert reg_msg['type'] == 'register'
        assert reg_msg['username'] == 'alice'
        pk_msg = json.loads(fake_ws.sent[1])
        assert pk_msg['type'] == 'public_key'
        # listener_task was created
        assert m.listener_task is not None

    @pytest.mark.asyncio
    async def test_connect_failure(self, capsys):
        m = SpectreMessenger("alice")

        async def fail_connect(*args, **kwargs):
            raise Exception("connection refused")

        with patch('messenger.websockets.connect', side_effect=fail_connect):
            await m.connect_to_server()

        assert m.connected is False
        captured = capsys.readouterr()
        assert "Failed to connect" in captured.out


class TestListenForMessages:
    @pytest.mark.asyncio
    async def test_handles_registered_message(self, capsys):
        m = SpectreMessenger("alice")
        m.connected = True
        m.websocket = FakeWebSocket([
            json.dumps({'type': 'registered', 'username': 'alice'})
        ])

        await m._listen_for_messages()
        captured = capsys.readouterr()
        assert "Registered as alice" in captured.out

    @pytest.mark.asyncio
    async def test_handles_user_list(self):
        m = SpectreMessenger("alice")
        m.connected = True
        m.websocket = FakeWebSocket([
            json.dumps({'type': 'user_list', 'users': ['alice', 'bob', 'charlie']})
        ])

        await m._listen_for_messages()
        assert m.online_users == {'bob', 'charlie'}

    @pytest.mark.asyncio
    async def test_handles_public_key_from_peer(self):
        m = SpectreMessenger("alice")
        m.connected = True
        m.websocket = FakeWebSocket([
            json.dumps({'type': 'public_key', 'username': 'bob', 'public_key': 'aa' * 32})
        ])

        await m._listen_for_messages()
        assert 'bob' in m.peers
        assert m.peers['bob'] == bytes.fromhex('aa' * 32)

    @pytest.mark.asyncio
    async def test_ignores_own_public_key(self):
        m = SpectreMessenger("alice")
        m.connected = True
        m.websocket = FakeWebSocket([
            json.dumps({'type': 'public_key', 'username': 'alice', 'public_key': 'bb' * 32})
        ])

        await m._listen_for_messages()
        assert 'alice' not in m.peers

    @pytest.mark.asyncio
    async def test_handles_error_message(self, capsys):
        m = SpectreMessenger("alice")
        m.connected = True
        m.websocket = FakeWebSocket([
            json.dumps({'type': 'error', 'message': 'something went wrong'})
        ])

        await m._listen_for_messages()
        captured = capsys.readouterr()
        assert "something went wrong" in captured.out

    @pytest.mark.asyncio
    async def test_handles_invalid_json(self, capsys):
        m = SpectreMessenger("alice")
        m.connected = True
        m.websocket = FakeWebSocket(["not json{{{"])

        await m._listen_for_messages()
        captured = capsys.readouterr()
        assert "Failed to parse" in captured.out

    @pytest.mark.asyncio
    async def test_handles_connection_closed(self):
        import websockets

        class ConnectionClosedWS:
            async def __aiter__(self):
                raise websockets.exceptions.ConnectionClosed(None, None)
                yield  # make this an async generator

        m = SpectreMessenger("alice")
        m.connected = True
        m.websocket = ConnectionClosedWS()

        await m._listen_for_messages()
        assert m.connected is False

    @pytest.mark.asyncio
    async def test_handles_incoming_message(self):
        alice = SpectreMessenger("alice")
        bob = SpectreMessenger("bob")

        # Sync session salts so both sides derive the same shared secret
        bob.crypto._session_salt = alice.crypto._session_salt

        alice_pub = alice.crypto.public_key.public_bytes_raw()
        bob_pub = bob.crypto.public_key.public_bytes_raw()

        secret_alice = alice.crypto.derive_shared_secret(bob_pub)
        secret_bob = bob.crypto.derive_shared_secret(alice_pub)
        bob.shared_secrets["alice"] = secret_bob
        bob.connected = True

        msg_data = json.dumps({
            'content': "listener test",
            'timestamp': time.time(),
            'nonce': base64.b64encode(os.urandom(16)).decode()
        })
        encrypted = alice.crypto.encrypt_message(msg_data, secret_alice)
        wrapped = base64.b64encode(encrypted).decode()

        bob.websocket = FakeWebSocket([json.dumps({
            'type': 'message',
            'from': 'alice',
            'encrypted_data': wrapped
        })])

        await bob._listen_for_messages()
        assert len(bob.message_history) == 1
        assert bob.message_history[0]['content'] == "listener test"


class TestEstablishSecureChannel:
    @pytest.mark.asyncio
    async def test_establish_with_known_peer(self):
        alice = SpectreMessenger("alice")
        bob = SpectreMessenger("bob")

        bob_pub = bob.crypto.public_key.public_bytes_raw()
        alice.peers["bob"] = bob_pub

        await alice._establish_secure_channel("bob")
        assert "bob" in alice.shared_secrets
        assert len(alice.shared_secrets["bob"]) == 32

    @pytest.mark.asyncio
    async def test_establish_without_peer_key_times_out(self):
        alice = SpectreMessenger("alice")
        alice.peers = {}  # No peer keys

        # Should timeout waiting for key
        # Patch asyncio.sleep to return immediately
        async def fast_sleep(t):
            pass

        with patch('asyncio.sleep', side_effect=fast_sleep):
            await alice._establish_secure_channel("unknown")
        assert "unknown" not in alice.shared_secrets
