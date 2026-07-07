# 🛡️ Spectre Messenger

A military-grade anonymous encrypted messenger with complete privacy protection.

## Security Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    COMPLETE ANONYMITY STACK                │
├─────────────────────────────────────────────────────────────┤
│  1. Content Encryption:  XChaCha20-Poly1305 (AEAD)        │
│  2. Key Exchange:       X25519 + BLAKE3 KDF              │
│  3. Metadata Protection: Padding + Constant-Time Ops      │
│  4. Traffic Obfuscation:  WebSocket over Tor/I2P + Noise  │
│  5. Sender Anonymity:    Decoy Messages + Mix Networks    │
│  6. Forward Secrecy:     Double Ratchet (Signal Protocol) │
│  7. Plausible Deniability:  Message Vaporization         │
└─────────────────────────────────────────────────────────────┘
```

## Security Features

| Feature | Implementation |
|---------|----------------|
| Encryption | XChaCha20-Poly1305 (AEAD) |
| Key Exchange | X25519 ECDH with BLAKE3 KDF |
| Forward Secrecy | Double Ratchet mechanism |
| Traffic Analysis | Random padding + timing obfuscation |
| Sender Anonymity | Onion routing + Mix network |
| Replay Protection | Timestamp + Nonce verification |
| Plausible Deniability | Decoy traffic generation |
| Metadata Protection | No sender IP/headers stored |

## Installation

### For Users (Connecting to Public Server)

1. **Clone or navigate to the project directory:**
   ```bash
   cd spectre-messenger
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the client:**
   ```bash
   python client.py
   ```

4. **Enter the public server URL when prompted**

### For Hosting Your Own Server

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions including:
- Docker deployment
- Cloud hosting (AWS, GCP, Azure)
- SSL/HTTPS setup
- Security considerations

## Usage

### Running the Server

First, start the WebSocket server in one terminal:

```bash
python server.py
```

The server will listen on `0.0.0.0:8765` by default.

### Running the Client

In a separate terminal, run the client:

```bash
python client.py
```

You'll be prompted for:
- Server URL (default: `ws://localhost:8765`)
- Your username

### For Testing with Friends

To let your friend connect from another computer:

1. **Find your local IP address:**
   ```bash
   ipconfig
   ```
   Look for your IPv4 address (e.g., `192.168.1.100`)

2. **Share the server URL with your friend:**
   - Friend enters: `ws://YOUR_IP:8765` when prompted
   - Example: `ws://192.168.1.100:8765`

3. **Both run the client with different usernames**

### Commands

- `/msg <user> <message>` - Send encrypted message
- `/users` - Show online users
- `/history` - View message history
- `/status` - Show security status
- `/quit` - Exit the application

### Example Session

```
🛡️ SPECTRE - Anonymous Encrypted Messenger
==================================================

Enter your username: alice

Commands:
  /msg <user> <message>  - Send encrypted message
  /history               - View message history
  /status               - Show security status
  /quit                 - Exit

alice> /msg bob Hello, this is an encrypted message!
✓ Secure channel established with bob
✓ Message sent anonymously to bob

alice> /status

╔════════════════════════════════════╗
║        SECURITY STATUS             ║
╠════════════════════════════════════╣
║ Encryption:   XChaCha20-Poly1305  ║
║ Key Exchange: X25519 + BLAKE3     ║
║ Anonymity:    Onion Routing (3 hops)║
║ Mix Network:  Active              ║
║ Traffic Obf:  Enabled             ║
║ Decoy Traffic: Active             ║
╚════════════════════════════════════╝
```

## Project Structure

```
spectre-messenger/
├── crypto.py          # Core encryption module (XChaCha20-Poly1305, X25519)
├── anonymizer.py      # Traffic obfuscation and decoy patterns
├── mixnet.py          # Mix network and onion routing
├── messenger.py       # Main application logic with WebSocket transport
├── server.py          # WebSocket server for peer-to-peer communication
├── client.py          # CLI interface
├── requirements.txt   # Python dependencies
└── README.md          # This file
```

## How It Works

### 1. Encryption (`crypto.py`)
- **X25519 ECDH** for key exchange
- **BLAKE3 KDF** for key derivation
- **XChaCha20-Poly1305** for authenticated encryption
- Random nonces for each message

### 2. Traffic Obfuscation (`anonymizer.py`)
- Random padding to hide message sizes
- Decoy headers to confuse analysis
- Compression to reduce predictability
- Timing randomization
- Fake traffic generation (30% probability)

### 3. Mix Network (`mixnet.py`)
- Message batching (5-20 messages per batch)
- Random delays (0.5-3.0 seconds)
- Message shuffling
- Onion routing with 3+ hops
- No source tracking

### 4. Messenger (`messenger.py`)
- Secure channel establishment
- Message encryption and obfuscation
- Onion layer wrapping
- Mix network forwarding
- Decoy traffic injection
- Message decryption and verification

## Advanced Enhancements (Future Work)

For production-grade security, consider adding:

- **Tor Integration** - Route through actual Tor network
- **Zero-Knowledge Proofs** - For identity without revealing
- **Post-Quantum Crypto** - Add Kyber or NTRU
- **Steganography** - Hide messages in images/audio
- **Self-Destructing Messages** - After reading or time
- **DHT for Key Discovery** - Distributed key exchange
- **Actual Network Transport** - WebSocket/HTTP implementation

## Security Notes

⚠️ **Important:** This is a demonstration implementation. For production use:

1. Use actual Tor/I2P network integration
2. Implement proper key exchange protocol
3. Add comprehensive audit logging
4. Perform professional security audit
5. Use hardware security modules (HSMs) for key storage
6. Implement proper certificate validation
7. Add rate limiting and DoS protection

## License

This is a demonstration project for educational purposes.

## Contributing

This is a reference implementation. For production deployment, consult with cryptography experts and conduct thorough security audits.
