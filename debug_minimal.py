import hashlib
import hmac
import os

print("Imported hashlib, hmac, os")

def sha256(data):
    return hashlib.sha256(data).digest()

print(sha256(b"test").hex())
print("Success")
