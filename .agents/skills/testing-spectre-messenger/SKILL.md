---
name: testing-spectre-messenger
description: Test the spectre-messenger unit test suite end-to-end. Use when verifying test changes, coverage, or crypto/network module correctness.
---

# Testing spectre-messenger

## Quick Start

```bash
cd /home/ubuntu/repos/spectre-messenger
pip install -r requirements.txt
pip install pytest pytest-cov pytest-asyncio
python -m pytest tests/ -v
```

## Commands

- **Run all tests**: `python -m pytest tests/ -v`
- **Run with coverage**: `python -m pytest tests/ --cov=. --cov-report=term-missing`
- **Run specific module**: `python -m pytest tests/test_crypto.py -v`
- **Run by keyword**: `python -m pytest tests/ -v -k "roundtrip or encrypt"`

## Test Structure

| Test File | Module Tested | Key Areas |
|-----------|---------------|-----------|
| `test_crypto.py` | `crypto.py` | X25519 key exchange, ChaCha20-Poly1305 encrypt/decrypt, tamper detection |
| `test_anonymizer.py` | `anonymizer.py` | Packet obfuscate/deobfuscate, padding, decoy traffic |
| `test_mixnet.py` | `mixnet.py` | MixNode batching, OnionRouter circuits, onion wrap/unwrap |
| `test_messenger.py` | `messenger.py` | Message dataclass, send/receive, secure channel, replay protection |
| `test_server.py` | `server.py` | Registration, message routing, handle_client flow |
| `test_client.py` | `client.py` | CLI commands (/msg, /users, /history, /status, /tip, /quit) |

## Known Issues

### Session salt and shared secret derivation
`SpectreCrypto` uses a random `_session_salt` per instance. When testing bidirectional crypto (Alice encrypts, Bob decrypts), you MUST sync the salt:
```python
bob.crypto._session_salt = alice.crypto._session_salt
```
Without this, `derive_shared_secret` produces different results for each party, and decryption fails silently.

### Test isolation with websockets
`server.py` uses `websockets.exceptions.ConnectionClosed` via lazy attribute access. Tests that reference this may fail when `test_server.py` runs in isolation because the `websockets.exceptions` submodule hasn't been imported yet. The full suite passes because `test_messenger.py` triggers the import first. If you see `AttributeError: module 'websockets' has no attribute 'exceptions'`, run the full suite instead of individual files.

### Async testing patterns
Tests use `FakeWebSocket` classes to mock WebSocket connections for `async for` iteration:
```python
class FakeWebSocket:
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
```
Do NOT use `AsyncMock` with `__aiter__` — it doesn't support `async for` properly.

### Listener done callback
`connect_to_server` creates a listener task with `_on_listener_done` callback that sets `connected = False` when the listener finishes. When testing with an empty `FakeWebSocket`, the listener completes immediately, so don't assert `connected is True` after `connect_to_server` — assert on `listener_task is not None` and sent messages instead.

### Replay window
The replay window is 30 seconds (`REPLAY_WINDOW_SECONDS`). Expired message tests should use timestamps > 30 seconds old.

## Configuration

- `pytest.ini` sets `asyncio_mode = auto` (no need for `@pytest.mark.asyncio` on every test, but it's good practice)
- No CI is configured on this repo — tests must be run locally

## Devin Secrets Needed

None — this is a local-only test suite with no external service dependencies.
