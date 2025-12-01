import time
import sys
import os
import requests
import binascii

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.time_keeper import TimeKeeper
from src.alice import alice_compute_public_history, alice_compute_checksum, alice_derive_final_key, alice_decrypt

BASE_URL = "http://127.0.0.1:5001"

def attempt_decrypt(ciphertext_hex, nonce_hex, pub_seed_hex, pub_salt_hex, t_start, t_end):
    # 1. Reconstruct bytes
    ciphertext = binascii.unhexlify(ciphertext_hex)
    nonce = binascii.unhexlify(nonce_hex)
    pub_seed = binascii.unhexlify(pub_seed_hex)
    pub_salt = binascii.unhexlify(pub_salt_hex)

    # 2. Compute Checksum
    history = alice_compute_public_history(pub_seed, pub_salt, t_end)
    checksum = alice_compute_checksum(history, t_start, t_end)

    # 3. Request Keys
    # Generate a unique nonce for the verify request
    verify_nonce = os.urandom(8).hex()
    
    resp = requests.post(f"{BASE_URL}/verify", json={
        "checksum": binascii.hexlify(checksum).decode(),
        "t_start": t_start,
        "t_end": t_end,
        "request_nonce": verify_nonce
    })

    if resp.status_code != 200:
        return False, resp.text

    keys = resp.json()
    k_pub = binascii.unhexlify(keys["k_public"])
    k_priv = binascii.unhexlify(keys["k_private"])

    # 4. Decrypt
    k_final = alice_derive_final_key(k_pub, k_priv)
    try:
        decrypted = alice_decrypt(ciphertext, k_final, nonce)
        return True, decrypted.decode()
    except Exception as e:
        return False, str(e)

def run_test():
    print("Initializing TimeKeeper...")
    tk = TimeKeeper(base_url=BASE_URL)
    tk.sync()
    tk.start()

    print("\n--- TEST 1: The Impatient User (Too Early) ---")
    current_t = tk.get_time()
    target_t = current_t + 5
    
    print(f"Encrypting for T={target_t} (Current T={current_t})")
    
    # Encrypt
    try:
        # Generate a unique nonce for the encrypt request
        encrypt_nonce = os.urandom(8).hex()
        
        resp = requests.post(f"{BASE_URL}/encrypt", json={
            "plaintext": binascii.hexlify(b"Secret Message").decode(),
            "t_start": current_t,
            "t_end": target_t,
            "request_nonce": encrypt_nonce
        })
        if resp.status_code != 200:
            print(f"Encryption failed: {resp.text}")
            return
        data = resp.json()
    except Exception as e:
        print(f"Connection error: {e}")
        return
    
    print("Waiting 2 seconds...")
    time.sleep(2)
    
    print(f"Attempting decrypt at Local T={tk.get_time()} (Target T={target_t})")
    success, result = attempt_decrypt(
        data['ciphertext'], data['nonce'], data['public_seed'], data['public_salt'], 
        data['t_start'], data['t_end']
    )
    
    if not success:
        print(f"Expected Failure: {result}")
    else:
        print(f"UNEXPECTED SUCCESS: {result}")

    print("\n--- TEST 2: The Patient User (Just Right) ---")
    
    # Wait loop to catch the exact moment
    while True:
        now = tk.get_time()
        if now >= target_t:
            break
        print(f"Waiting... Local T={now} Target T={target_t}")
        time.sleep(0.5)
    
    print(f"Attempting decrypt at Local T={tk.get_time()} (Target T={target_t})")
    success, result = attempt_decrypt(
        data['ciphertext'], data['nonce'], data['public_seed'], data['public_salt'], 
        data['t_start'], data['t_end']
    )
    
    if success:
        print(f"SUCCESS: {result}")
    else:
        print(f"FAILURE: {result}")

    tk.stop()

if __name__ == "__main__":
    run_test()
