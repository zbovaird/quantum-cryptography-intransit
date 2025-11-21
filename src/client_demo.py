import requests
import binascii
from src.alice import alice_compute_public_history, alice_compute_checksum, alice_derive_final_key, alice_decrypt

BASE_URL = "http://localhost:5000"

def run_client_demo():
    print("--- Starting HTTP Client Demo ---")
    
    # 1. Encrypt
    plaintext = b"Hello via HTTP!"
    t_start = 20
    t_end = 25
    
    print(f"Requesting encryption for '{plaintext.decode()}' window [{t_start}, {t_end}]...")
    resp = requests.post(f"{BASE_URL}/encrypt", json={
        "plaintext": binascii.hexlify(plaintext).decode(),
        "t_start": t_start,
        "t_end": t_end
    })
    
    if resp.status_code != 200:
        print(f"Encryption failed: {resp.text}")
        return
        
    data = resp.json()
    ciphertext = binascii.unhexlify(data["ciphertext"])
    pub_seed = binascii.unhexlify(data["public_seed"])
    pub_salt = binascii.unhexlify(data["public_salt"])
    print(f"Got ciphertext: {data['ciphertext']}")
    
    # 2. Alice Work
    print("Computing public chain...")
    history = alice_compute_public_history(pub_seed, pub_salt, t_end)
    checksum = alice_compute_checksum(history, t_start, t_end)
    
    # 3. Verify
    print("Submitting checksum...")
    resp = requests.post(f"{BASE_URL}/verify", json={
        "checksum": binascii.hexlify(checksum).decode(),
        "t_start": t_start,
        "t_end": t_end
    })
    
    if resp.status_code != 200:
        print(f"Verification failed: {resp.text}")
        return
        
    keys = resp.json()
    k_pub = binascii.unhexlify(keys["k_public"])
    k_priv = binascii.unhexlify(keys["k_private"])
    print("Got keys from server.")
    
    # 4. Decrypt
    k_final = alice_derive_final_key(k_pub, k_priv, len(ciphertext))
    decrypted = alice_decrypt(ciphertext, k_final)
    print(f"Decrypted: {decrypted}")
    
    if decrypted == plaintext:
        print("SUCCESS")
    else:
        print("FAILURE")

if __name__ == "__main__":
    run_client_demo()
