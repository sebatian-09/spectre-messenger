import asyncio
import sys
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from io import StringIO

import client


class TestClientMain:
    @pytest.mark.asyncio
    async def test_exits_when_connection_fails(self):
        inputs = iter(["ws://localhost:9999", "testuser"])
        with patch('builtins.input', side_effect=inputs):
            with patch('messenger.SpectreMessenger.connect_to_server', new_callable=AsyncMock):
                await client.main()

    @pytest.mark.asyncio
    async def test_default_server_url_when_empty(self):
        inputs = iter(["", "testuser"])
        captured_messenger = {}

        original_init = client.SpectreMessenger.__init__

        def capture_init(self, username, server_url='ws://localhost:8765'):
            captured_messenger['url'] = server_url
            original_init(self, username, server_url)

        with patch('builtins.input', side_effect=inputs):
            with patch('messenger.SpectreMessenger.__init__', capture_init):
                with patch('messenger.SpectreMessenger.connect_to_server', new_callable=AsyncMock):
                    await client.main()

        assert captured_messenger['url'] == 'ws://localhost:8765'

    @pytest.mark.asyncio
    async def test_msg_command(self):
        inputs = iter(["ws://localhost:8765", "alice"])

        async def fake_connect(self):
            self.connected = True

        call_count = {'n': 0}

        async def fake_to_thread(fn, prompt):
            call_count['n'] += 1
            if call_count['n'] == 1:
                return "/msg bob hello there"
            elif call_count['n'] == 2:
                return "/quit"
            return "/quit"

        with patch('builtins.input', side_effect=inputs):
            with patch.object(client.SpectreMessenger, 'connect_to_server', fake_connect):
                with patch('asyncio.to_thread', side_effect=fake_to_thread):
                    with patch.object(client.SpectreMessenger, 'send_message', new_callable=AsyncMock) as mock_send:
                        with pytest.raises(SystemExit):
                            await client.main()
                        mock_send.assert_called_once_with("bob", "hello there")

    @pytest.mark.asyncio
    async def test_users_command(self, capsys):
        inputs = iter(["ws://localhost:8765", "alice"])

        async def fake_connect(self):
            self.connected = True
            self.online_users = {"bob", "charlie"}

        call_count = {'n': 0}

        async def fake_to_thread(fn, prompt):
            call_count['n'] += 1
            if call_count['n'] == 1:
                return "/users"
            return "/quit"

        with patch('builtins.input', side_effect=inputs):
            with patch.object(client.SpectreMessenger, 'connect_to_server', fake_connect):
                with patch('asyncio.to_thread', side_effect=fake_to_thread):
                    with pytest.raises(SystemExit):
                        await client.main()
        captured = capsys.readouterr()
        assert "bob" in captured.out or "charlie" in captured.out

    @pytest.mark.asyncio
    async def test_history_command(self, capsys):
        inputs = iter(["ws://localhost:8765", "alice"])

        async def fake_connect(self):
            self.connected = True
            self.message_history = [
                {'from': 'bob', 'content': 'hi alice', 'timestamp': 1000.0}
            ]

        call_count = {'n': 0}

        async def fake_to_thread(fn, prompt):
            call_count['n'] += 1
            if call_count['n'] == 1:
                return "/history"
            return "/quit"

        with patch('builtins.input', side_effect=inputs):
            with patch.object(client.SpectreMessenger, 'connect_to_server', fake_connect):
                with patch('asyncio.to_thread', side_effect=fake_to_thread):
                    with pytest.raises(SystemExit):
                        await client.main()
        captured = capsys.readouterr()
        assert "hi alice" in captured.out

    @pytest.mark.asyncio
    async def test_status_command(self, capsys):
        inputs = iter(["ws://localhost:8765", "alice"])

        async def fake_connect(self):
            self.connected = True

        call_count = {'n': 0}

        async def fake_to_thread(fn, prompt):
            call_count['n'] += 1
            if call_count['n'] == 1:
                return "/status"
            return "/quit"

        with patch('builtins.input', side_effect=inputs):
            with patch.object(client.SpectreMessenger, 'connect_to_server', fake_connect):
                with patch('asyncio.to_thread', side_effect=fake_to_thread):
                    with pytest.raises(SystemExit):
                        await client.main()
        captured = capsys.readouterr()
        assert "ChaCha20" in captured.out

    @pytest.mark.asyncio
    async def test_tip_command(self, capsys):
        inputs = iter(["ws://localhost:8765", "alice"])

        async def fake_connect(self):
            self.connected = True

        call_count = {'n': 0}

        async def fake_to_thread(fn, prompt):
            call_count['n'] += 1
            if call_count['n'] == 1:
                return "/tip"
            return "/quit"

        with patch('builtins.input', side_effect=inputs):
            with patch.object(client.SpectreMessenger, 'connect_to_server', fake_connect):
                with patch('asyncio.to_thread', side_effect=fake_to_thread):
                    with pytest.raises(SystemExit):
                        await client.main()
        captured = capsys.readouterr()
        assert "SUPPORT" in captured.out

    @pytest.mark.asyncio
    async def test_quit_command(self):
        inputs = iter(["ws://localhost:8765", "alice"])

        async def fake_connect(self):
            self.connected = True
            self.websocket = AsyncMock()

        call_count = {'n': 0}

        async def fake_to_thread(fn, prompt):
            call_count['n'] += 1
            return "/quit"

        with patch('builtins.input', side_effect=inputs):
            with patch.object(client.SpectreMessenger, 'connect_to_server', fake_connect):
                with patch('asyncio.to_thread', side_effect=fake_to_thread):
                    with pytest.raises(SystemExit):
                        await client.main()

    @pytest.mark.asyncio
    async def test_invalid_msg_usage(self, capsys):
        inputs = iter(["ws://localhost:8765", "alice"])

        async def fake_connect(self):
            self.connected = True

        call_count = {'n': 0}

        async def fake_to_thread(fn, prompt):
            call_count['n'] += 1
            if call_count['n'] == 1:
                return "/msg onlyuser"
            return "/quit"

        with patch('builtins.input', side_effect=inputs):
            with patch.object(client.SpectreMessenger, 'connect_to_server', fake_connect):
                with patch('asyncio.to_thread', side_effect=fake_to_thread):
                    with pytest.raises(SystemExit):
                        await client.main()
        captured = capsys.readouterr()
        assert "Usage:" in captured.out

    @pytest.mark.asyncio
    async def test_keyboard_interrupt(self):
        inputs = iter(["ws://localhost:8765", "alice"])

        async def fake_connect(self):
            self.connected = True
            self.websocket = AsyncMock()

        async def fake_to_thread(fn, prompt):
            raise KeyboardInterrupt()

        with patch('builtins.input', side_effect=inputs):
            with patch.object(client.SpectreMessenger, 'connect_to_server', fake_connect):
                with patch('asyncio.to_thread', side_effect=fake_to_thread):
                    with pytest.raises(SystemExit):
                        await client.main()

    @pytest.mark.asyncio
    async def test_generic_exception_in_loop(self, capsys):
        inputs = iter(["ws://localhost:8765", "alice"])

        async def fake_connect(self):
            self.connected = True

        call_count = {'n': 0}

        async def fake_to_thread(fn, prompt):
            call_count['n'] += 1
            if call_count['n'] == 1:
                raise ValueError("something broke")
            return "/quit"

        with patch('builtins.input', side_effect=inputs):
            with patch.object(client.SpectreMessenger, 'connect_to_server', fake_connect):
                with patch('asyncio.to_thread', side_effect=fake_to_thread):
                    with pytest.raises(SystemExit):
                        await client.main()
        captured = capsys.readouterr()
        assert "Error:" in captured.out
