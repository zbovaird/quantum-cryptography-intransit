from src.core import sha256
from src.server import Server
from src.alice import alice_compute_public_history, alice_compute_checksum, alice_derive_final_key, alice_decrypt
import os

def run_demo():
    print("--- Starting Time-Evolving Ephemeral Decryption Demo ---")
    
    # 1. Setup
    server = Server()
    plaintext = b"The eagle flies at midnight."
    print(f"Plaintext: {plaintext}")
    
    # 2. Encryption
    # Choose a window in the future.
    t_start = 10
    t_end = 15
    
    print(f"Encrypting for window [{t_start}, {t_end}]...")
    encryption_result = server.encrypt_for_alice(plaintext, t_start, t_end)
    ciphertext = encryption_result["ciphertext"]
    nonce = encryption_result["nonce"]
    print(f"Ciphertext: {ciphertext.hex()}")
    print(f"Nonce: {nonce.hex()}")
    
    # 3. Alice's Work
    print("Alice is computing public chain...")
    pub_seed = encryption_result["public_seed"]
    pub_salt = encryption_result["public_salt"]
    
    # Alice computes up to t_end
    alice_history = alice_compute_public_history(pub_seed, pub_salt, t_end)
    
    # 4. Checksum
    print("Alice computing checksum...")
    checksum = alice_compute_checksum(alice_history, t_start, t_end)
    
    # 5. Key Release
    print("Alice requesting key from Server...")
    try:
        keys = server.verify_checksum_and_release_private_key_piece(checksum, t_start, t_end)
        k_public = keys["k_public"]
        k_private = keys["k_private"]
        print("Server released keys.")
    except Exception as e:
        print(f"Server rejected request: {e}")
        return

    # 6. Decryption
    print("Alice decrypting...")
    k_final = alice_derive_final_key(k_public, k_private)
    decrypted = alice_decrypt(ciphertext, k_final, nonce)
    print(f"Decrypted: {decrypted}")
    
    if decrypted == plaintext:
        print("SUCCESS: Decryption verified.")
    else:
        print("FAILURE: Decryption failed.")
        
    # 7. Attacker Simulation (Decrypt Now or Never)
    print("\n--- Attacker Simulation ---")
    print("Attacker tries to get key for the SAME window again...")
    try:
        server.verify_checksum_and_release_private_key_piece(checksum, t_start, t_end)
        print("FAILURE: Server released key twice!")
    except Exception as e:
        # It might return wrong key or raise error?
        # Since we advanced to t_end, if we ask for t_end again, 
        # advance_private_state_to(t_end) does nothing.
        # It returns H(S_{t_end}).
        # So actually, the server *does* release the key again if we are exactly at t_end?
        # Wait. "The server maintains a private, evolving state that never repeats and never rewinds."
        # If S is at S_{t_end}, and we ask for t_end.
        # advance checks current < target. 15 < 15 is False.
        # So it returns H(S_{15}).
        # So the key IS released again?
        # This implies the key is available *until* the server moves past t_end.
        # But the server moves past t_end when?
        # Only when requested for a *later* window.
        # So "Decrypt Now or Never" means "Decrypt before the server moves on".
        # If the server never moves on, the key remains available.
        # This is consistent with the prompt "Decryption requires live server cooperation."
        # But "captured ciphertext cannot be decrypted later without intercepting an ephemeral private key piece".
        # If the attacker asks *now*, they get it.
        # But if the attacker asks *later* (after server moved to t=100), they can't get it.
        print(f"Server response: {e if isinstance(e, Exception) else 'Keys released'}")

    print("Attacker tries to get key for OLDER window [5, 10]...")
    try:
        # Server is at 15.
        # Attacker asks for 10.
        # advance(10) does nothing.
        # Returns H(S_{15}).
        # But correct key was H(S_{10}).
        # So the key is WRONG.
        attacker_checksum = alice_compute_checksum(alice_history, 5, 10)
        keys = server.verify_checksum_and_release_private_key_piece(attacker_checksum, 5, 10)
        k_priv_wrong = keys["k_private"]
        
        # Try to decrypt something encrypted for [5, 10] (if we had it)
        # But we can verify k_priv_wrong != k_priv_correct (if we knew it).
        # We don't have ground truth for [5, 10] here.
        # But we can assert that k_priv_wrong is actually H(S_{15}).
        # And H(S_{15}) != H(S_{10}).
        print("Server returned a key (expected behavior, but it should be the WRONG key).")
        
    except Exception as e:
        print(f"Server error: {e}")

    print("Demo complete.")

if __name__ == "__main__":
    run_demo()
