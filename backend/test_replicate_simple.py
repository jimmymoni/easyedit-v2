"""
Simple test to verify Replicate API connectivity
"""
import os
import replicate
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Get API token
api_token = os.getenv('REPLICATE_API_TOKEN')

if not api_token:
    print("[ERROR] REPLICATE_API_TOKEN not found in environment!")
    exit(1)

print(f"[OK] Found REPLICATE_API_TOKEN: {api_token[:10]}...")

# Configure client
os.environ["REPLICATE_API_TOKEN"] = api_token

try:
    print("\n[TEST] Testing Replicate API with simple model...")
    print("       Using: hello-world model (quick test)")

    # Use a simple, fast model for testing connectivity
    output = replicate.run(
        "replicate/hello-world:5c7d5dc6dd8bf75c1acaa8565735e7986bc5b66206b55cca93cb72c9bf15ccaa",
        input={"text": "Hello from EasyEdit!"}
    )

    print(f"\n[SUCCESS] Replicate API is working!")
    print(f"          Response: {output}")

except Exception as e:
    print(f"\n[ERROR] {type(e).__name__}: {str(e)}")
    print("\nThis suggests a network connectivity issue, not an API key problem.")
    print("\nPossible causes:")
    print("  1. Antivirus/Windows Firewall blocking the connection")
    print("  2. VPN interfering with HTTPS connections")
    print("  3. Corporate proxy requiring configuration")
    print("  4. Network timeout on long-running requests")
    exit(1)
