import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

try:
    print("Importing src.core...")
    from src.core import sha256, hkdf, evolve_public_chain
    print("Import success.")

    print("Testing sha256...")
    h = sha256(b"test")
    print(f"SHA256: {h.hex()}")

    print("Testing HKDF...")
    k = hkdf(b"key", 32)
    print(f"HKDF: {k.hex()}")
    
    print("Testing evolve_public_chain...")
    chain = evolve_public_chain(b"\x00"*32, b"\x00"*32, 5)
    print(f"Chain length: {len(chain)}")
    
    print("All checks passed.")
except Exception as e:
    print(f"Error: {e}")
