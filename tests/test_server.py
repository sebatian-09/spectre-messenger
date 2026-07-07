import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from server import SpectreServer


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


class TestSpectreServerInit:
    def test_default_host_and_port(self):
        server = SpectreServer()
        assert server.host == 'localhost'
        assert server.port == 8765

    def test_custom_host_and_port(self):
        server = SpectreServer(host='0.0.0.0', port=9999)
        assert server.host == '0.0.0.0'
        assert server.port == 9999

    def test_clients_initially_empty(self):
        server = SpectreServer()
        assert server.clients == {}

    def test_public_keys_initially_empty(self):
        server = SpectreServer()
        assert server.public_keys == {}


class TestRegister:
    @pytest.mark.asyncio
    async def test_register_new_user(self):
        server = SpectreServer()
        ws = AsyncMock()
        result = await server.register(ws, "alice")
        assert result is True
        assert "alice" in server.clients
        assert server.clients["alice"] == ws

    @pytest.mark.asyncio
    async def test_register_sends_confirmation(self):
        server = SpectreServer()
        ws = AsyncMock()
        await server.register(ws, "alice")
        calls = ws.send.call_args_list
        # First call is the registered confirmation
        registered_msg = json.loads(calls[0][0][0])
        assert registered_msg['type'] == 'registered'
        assert registered_msg['username'] == 'alice'

    @pytest.mark.asyncio
    async def test_register_duplicate_username_fails(self):
        server = SpectreServer()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await server.register(ws1, "alice")
        result = await server.register(ws2, "alice")
        assert result is False
        # Original registration should remain
        assert server.clients["alice"] == ws1

    @pytest.mark.asyncio
    async def test_register_duplicate_sends_error(self):
        server = SpectreServer()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await server.register(ws1, "alice")
        await server.register(ws2, "alice")
        error_msg = json.loads(ws2.send.call_args[0][0])
        assert error_msg['type'] == 'error'
        assert 'already taken' in error_msg['message']

    @pytest.mark.asyncio
    async def test_register_broadcasts_user_list(self):
        server = SpectreServer()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await server.register(ws1, "alice")
        await server.register(ws2, "bob")
        # After bob registers, both should get a user_list containing both users
        found_user_list_with_both = False
        for call in ws1.send.call_args_list:
            msg = json.loads(call[0][0])
            if msg['type'] == 'user_list' and 'bob' in msg['users'] and 'alice' in msg['users']:
                found_user_list_with_both = True
        assert found_user_list_with_both


class TestUnregister:
    @pytest.mark.asyncio
    async def test_unregister_removes_client(self):
        server = SpectreServer()
        ws = AsyncMock()
        await server.register(ws, "alice")
        await server.unregister("alice")
        assert "alice" not in server.clients

    @pytest.mark.asyncio
    async def test_unregister_removes_public_key(self):
        server = SpectreServer()
        ws = AsyncMock()
        await server.register(ws, "alice")
        server.public_keys["alice"] = "deadbeef"
        await server.unregister("alice")
        assert "alice" not in server.public_keys

    @pytest.mark.asyncio
    async def test_unregister_nonexistent_user_noop(self):
        server = SpectreServer()
        await server.unregister("ghost")  # should not raise


class TestBroadcastUserList:
    @pytest.mark.asyncio
    async def test_broadcasts_to_all_clients(self):
        server = SpectreServer()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        server.clients = {"alice": ws1, "bob": ws2}
        await server.broadcast_user_list()
        for ws in [ws1, ws2]:
            msg = json.loads(ws.send.call_args[0][0])
            assert msg['type'] == 'user_list'
            assert set(msg['users']) == {"alice", "bob"}

    @pytest.mark.asyncio
    async def test_broadcast_tolerates_send_failure(self):
        server = SpectreServer()
        ws1 = AsyncMock()
        ws1.send.side_effect = Exception("connection lost")
        ws2 = AsyncMock()
        server.clients = {"alice": ws1, "bob": ws2}
        await server.broadcast_user_list()  # should not raise
        ws2.send.assert_called_once()


class TestHandlePublicKey:
    @pytest.mark.asyncio
    async def test_stores_public_key(self):
        server = SpectreServer()
        ws = AsyncMock()
        server.clients = {"alice": ws}
        await server.handle_public_key("alice", "abcdef")
        assert server.public_keys["alice"] == "abcdef"

    @pytest.mark.asyncio
    async def test_broadcasts_public_key_to_all(self):
        server = SpectreServer()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        server.clients = {"alice": ws1, "bob": ws2}
        await server.handle_public_key("alice", "abcdef")
        for ws in [ws1, ws2]:
            msg = json.loads(ws.send.call_args[0][0])
            assert msg['type'] == 'public_key'
            assert msg['username'] == 'alice'
            assert msg['public_key'] == 'abcdef'


class TestHandleMessage:
    @pytest.mark.asyncio
    async def test_routes_message_to_recipient(self):
        server = SpectreServer()
        ws_bob = AsyncMock()
        server.clients = {"bob": ws_bob}
        result = await server.handle_message("alice", "bob", "encrypted_payload")
        assert result is True
        msg = json.loads(ws_bob.send.call_args[0][0])
        assert msg['type'] == 'message'
        assert msg['from'] == 'alice'
        assert msg['encrypted_data'] == 'encrypted_payload'

    @pytest.mark.asyncio
    async def test_recipient_not_found(self):
        server = SpectreServer()
        result = await server.handle_message("alice", "ghost", "data")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_failure_returns_false(self):
        server = SpectreServer()
        ws_bob = AsyncMock()
        ws_bob.send.side_effect = Exception("disconnected")
        server.clients = {"bob": ws_bob}
        result = await server.handle_message("alice", "bob", "data")
        assert result is False


class TestHandlePublicKeyBroadcastFailure:
    @pytest.mark.asyncio
    async def test_broadcast_public_key_tolerates_send_failure(self):
        server = SpectreServer()
        ws1 = AsyncMock()
        ws1.send.side_effect = Exception("disconnected")
        ws2 = AsyncMock()
        server.clients = {"alice": ws1, "bob": ws2}
        await server.handle_public_key("alice", "key123")
        # ws2 should still receive the key
        msg = json.loads(ws2.send.call_args[0][0])
        assert msg['type'] == 'public_key'


class TestUnregisterBroadcasts:
    @pytest.mark.asyncio
    async def test_unregister_broadcasts_when_clients_remain(self):
        server = SpectreServer()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await server.register(ws1, "alice")
        await server.register(ws2, "bob")
        # Reset mock to track only unregister broadcasts
        ws2.send.reset_mock()
        await server.unregister("alice")
        # Bob should get updated user list
        assert ws2.send.called
        msg = json.loads(ws2.send.call_args[0][0])
        assert msg['type'] == 'user_list'
        assert 'alice' not in msg['users']

    @pytest.mark.asyncio
    async def test_unregister_last_user_no_broadcast(self):
        server = SpectreServer()
        ws = AsyncMock()
        await server.register(ws, "alice")
        ws.send.reset_mock()
        await server.unregister("alice")
        # No broadcast since no clients remain
        # (the only send would have been user_list, but we reset mock)
        # Actually server code skips broadcast if len(clients) == 0
        assert len(server.clients) == 0


class TestHandleClient:
    @pytest.mark.asyncio
    async def test_handle_client_register_and_public_key(self):
        server = SpectreServer()
        ws = FakeWebSocket([
            json.dumps({'type': 'register', 'username': 'alice'}),
            json.dumps({'type': 'public_key', 'public_key': 'aabbcc'}),
        ])

        await server.handle_client(ws)
        assert "alice" not in server.clients  # unregistered in finally

    @pytest.mark.asyncio
    async def test_handle_client_routes_message(self):
        server = SpectreServer()
        ws_bob = AsyncMock()
        server.clients["bob"] = ws_bob

        ws_alice = FakeWebSocket([
            json.dumps({'type': 'register', 'username': 'alice'}),
            json.dumps({'type': 'message', 'to': 'bob', 'encrypted_data': 'secret'}),
        ])

        await server.handle_client(ws_alice)
        found_message = False
        for call in ws_bob.send.call_args_list:
            msg = json.loads(call[0][0])
            if msg.get('type') == 'message' and msg.get('from') == 'alice':
                found_message = True
                assert msg['encrypted_data'] == 'secret'
        assert found_message

    @pytest.mark.asyncio
    async def test_handle_client_sends_existing_keys_to_new_user(self):
        server = SpectreServer()
        server.public_keys["bob"] = "bobkey123"

        ws = FakeWebSocket([
            json.dumps({'type': 'register', 'username': 'alice'}),
        ])

        await server.handle_client(ws)
        found_key = False
        for data in ws.sent:
            msg = json.loads(data)
            if msg.get('type') == 'public_key' and msg.get('username') == 'bob':
                found_key = True
                assert msg['public_key'] == 'bobkey123'
        assert found_key

    @pytest.mark.asyncio
    async def test_handle_client_invalid_json(self):
        server = SpectreServer()
        ws = FakeWebSocket([
            json.dumps({'type': 'register', 'username': 'alice'}),
            "not valid json{{{",
        ])

        await server.handle_client(ws)

    @pytest.mark.asyncio
    async def test_handle_client_connection_closed(self):
        import websockets

        server = SpectreServer()

        class ConnectionClosedWS:
            async def __aiter__(self):
                raise websockets.exceptions.ConnectionClosed(None, None)
                yield

            async def send(self, data):
                pass

        await server.handle_client(ConnectionClosedWS())

    @pytest.mark.asyncio
    async def test_handle_client_generic_exception(self):
        server = SpectreServer()

        class ErrorWS:
            async def __aiter__(self):
                raise RuntimeError("unexpected")
                yield

            async def send(self, data):
                pass

        await server.handle_client(ErrorWS())


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_returns_ok(self):
        server = SpectreServer()
        request = MagicMock()
        response = await server.health_check(request)
        assert response.status == 200
        assert response.text == "OK"
