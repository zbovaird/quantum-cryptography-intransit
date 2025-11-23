import argparse
import json
import requests
import binascii
import os
import sys
from src.alice import alice_compute_public_history, alice_compute_checksum, alice_derive_final_key, alice_decrypt

BASE_URL = "http://localhost:5001"

def encrypt_file(filepath, t_start, t_end):
    print(f"[*] Reading file: {filepath}")
    try:
        with open(filepath, 'rb') as f:
            plaintext = f.read()
    except FileNotFoundError:
        print(f"[!] Error: File not found: {filepath}")
        sys.exit(1)

    plaintext_hex = binascii.hexlify(plaintext).decode()
    
    print(f"[*] Requesting encryption for window [{t_start}, {t_end}]...")
    try:
        res = requests.post(f"{BASE_URL}/encrypt", json={
            "plaintext": plaintext_hex,
            "t_start": t_start,
            "t_end": t_end
        })
        
        if res.status_code != 200:
            print(f"[!] Server Error ({res.status_code}): {res.text}")
            sys.exit(1)
            
        data = res.json()
        
        # Save metadata + ciphertext
        output_path = f"{filepath}.enc"
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
            
        print(f"[+] Encrypted file saved to: {output_path}")
        print(f"    Ciphertext: {data['ciphertext'][:20]}...")
        print(f"    Window: [{t_start}, {t_end}]")
        
    except requests.exceptions.ConnectionError:
        print("[!] Error: Could not connect to server. Is it running on port 5001?")
        sys.exit(1)

def decrypt_file(enc_filepath):
    print(f"[*] Reading encrypted file: {enc_filepath}")
    try:
        with open(enc_filepath, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"[!] Error: File not found: {enc_filepath}")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"[!] Error: Invalid JSON format in {enc_filepath}")
        sys.exit(1)

    # Extract metadata
    try:
        ciphertext = binascii.unhexlify(data["ciphertext"])
        nonce = binascii.unhexlify(data["nonce"])
        pub_seed = binascii.unhexlify(data["public_seed"])
        pub_salt = binascii.unhexlify(data["public_salt"])
        t_start = data["t_start"]
        t_end = data["t_end"]
    except KeyError as e:
        print(f"[!] Error: Missing field in encrypted file: {e}")
        sys.exit(1)

    print(f"[*] Target Window: [{t_start}, {t_end}]")
    print("[*] Computing public hash chain (Proof of Time)...")
    
    # 1. Compute Chain
    history = alice_compute_public_history(pub_seed, pub_salt, t_end)
    
    # 2. Compute Checksum
    checksum = alice_compute_checksum(history, t_start, t_end)
    checksum_hex = binascii.hexlify(checksum).decode()
    
    print("[*] Verifying checksum with server...")
    try:
        res = requests.post(f"{BASE_URL}/verify", json={
            "checksum": checksum_hex,
            "t_start": t_start,
            "t_end": t_end
        })
        
        if res.status_code != 200:
            print(f"[!] Decryption Failed: {res.text}")
            sys.exit(1)
            
        keys = res.json()
        k_public = binascii.unhexlify(keys["k_public"])
        k_private = binascii.unhexlify(keys["k_private"])
        
        print("[+] Server verified checksum and released private key piece.")
        print("[*] Deriving final key...")
        
        k_final = alice_derive_final_key(k_public, k_private)
        
        print("[*] Decrypting...")
        decrypted_bytes = alice_decrypt(ciphertext, k_final, nonce)
        
        # Determine output filename (remove .enc if present, else add .dec)
        if enc_filepath.endswith(".enc"):
            output_path = enc_filepath[:-4]
        else:
            output_path = f"{enc_filepath}.dec"
            
        with open(output_path, 'wb') as f:
            f.write(decrypted_bytes)
            
        print(f"[+] Success! Decrypted file saved to: {output_path}")
        
    except Exception as e:
        print(f"[!] Error during decryption: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ephemeral File Encryption Demo")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Encrypt Command
    enc_parser = subparsers.add_parser("encrypt", help="Encrypt a file")
    enc_parser.add_argument("filepath", help="Path to the file to encrypt")
    enc_parser.add_argument("t_start", type=int, help="Start tick of the validity window")
    enc_parser.add_argument("t_end", type=int, help="End tick of the validity window")
    
    # Decrypt Command
    dec_parser = subparsers.add_parser("decrypt", help="Decrypt a file")
    dec_parser.add_argument("filepath", help="Path to the .enc file")
    
    args = parser.parse_args()
    
    if args.command == "encrypt":
        encrypt_file(args.filepath, args.t_start, args.t_end)
    elif args.command == "decrypt":
        decrypt_file(args.filepath)
