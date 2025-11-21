import sys
print("Starting debug_imports.py")
print(f"Python version: {sys.version}")

try:
    print("Importing hashlib...")
    import hashlib
    print("Success.")
except Exception as e:
    print(f"Failed: {e}")

try:
    print("Importing hmac...")
    import hmac
    print("Success.")
except Exception as e:
    print(f"Failed: {e}")

try:
    print("Importing src.core...")
    import src.core
    print("Success.")
except Exception as e:
    print(f"Failed: {e}")

try:
    print("Importing src.server...")
    import src.server
    print("Success.")
except Exception as e:
    print(f"Failed: {e}")

try:
    print("Importing src.alice...")
    import src.alice
    print("Success.")
except Exception as e:
    print(f"Failed: {e}")

print("All imports finished.")
