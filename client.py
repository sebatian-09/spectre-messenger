import asyncio
import sys
import getpass
from messenger import SpectreMessenger

async def main():
    print("🛡️ SPECTRE - Anonymous Encrypted Messenger")
    print("=" * 50)
    
    server_url = input("Enter server URL (default: ws://localhost:8765): ").strip()
    if not server_url:
        server_url = 'ws://localhost:8765'
    
    username = input("Enter your username: ")
    messenger = SpectreMessenger(username, server_url)
    
    # Connect to server
    await messenger.connect_to_server()
    
    if not messenger.connected:
        print("❌ Failed to connect to server. Exiting.")
        return
    
    print("\nCommands:")
    print("  /msg <user> <message>  - Send encrypted message")
    print("  /users                 - Show online users")
    print("  /history               - View message history")
    print("  /status               - Show security status")
    print("  /tip                   - Support the developer")
    print("  /quit                 - Exit\n")
    
    while True:
        try:
            cmd = await asyncio.to_thread(input, f"{username}> ")
            cmd = cmd.strip()
            
            if cmd.startswith("/msg"):
                parts = cmd.split(" ", 2)
                if len(parts) >= 3:
                    _, recipient, message = parts
                    await messenger.send_message(recipient, message)
                else:
                    print("Usage: /msg <user> <message>")
            
            elif cmd == "/users":
                print("\n📱 Online users:")
                if messenger.online_users:
                    for user in messenger.online_users:
                        print(f"  - {user}")
                else:
                    print("  No other users online")
                print()
            
            elif cmd == "/history":
                print("\n📜 Message History:")
                for msg in messenger.message_history[-10:]:
                    print(f"  {msg['from']}: {msg['content']}")
                print()
            
            elif cmd == "/status":
                print(f"""
╔════════════════════════════════════╗
║        SECURITY STATUS             ║
╠════════════════════════════════════╣
║ Encryption:   ChaCha20-Poly1305   ║
║ Key Exchange: X25519 + BLAKE3     ║
║ Network:      WebSocket Encrypted  ║
╚════════════════════════════════════╝
                """)
            
            elif cmd == "/tip":
                print(f"""
╔══════════════════════════════════════════════════╗
║            SUPPORT THE DEVELOPER                 ║
╠══════════════════════════════════════════════════╣
║  Bitcoin: bc1qrhldwx8f8075we5hqhsezc61gzhffhftvafefc ║
║                                                  ║
║  Your support keeps this free!                   ║
╚══════════════════════════════════════════════════╝
                """)
            
            elif cmd == "/quit":
                print("Goodbye!")
                if messenger.websocket:
                    await messenger.websocket.close()
                sys.exit(0)
                
        except KeyboardInterrupt:
            print("\nGoodbye!")
            if messenger.websocket:
                await messenger.websocket.close()
            sys.exit(0)
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
