import unittest
from src.server import Server
from src.alice import alice_compute_public_history, alice_compute_checksum, alice_derive_final_key, alice_decrypt

class TestProtocol(unittest.TestCase):
    def test_full_flow(self):
        server = Server()
        plaintext = b"secret message"
        t_start = 1
        t_end = 5
        
        # Encrypt
        result = server.encrypt_for_alice(plaintext, t_start, t_end)
        ciphertext = result["ciphertext"]
        pub_seed = result["public_seed"]
        pub_salt = result["public_salt"]
        
        # Alice work
        history = alice_compute_public_history(pub_seed, pub_salt, t_end)
        checksum = alice_compute_checksum(history, t_start, t_end)
        
        # Key release
        keys = server.verify_checksum_and_release_private_key_piece(checksum, t_start, t_end)
        k_pub = keys["k_public"]
        k_priv = keys["k_private"]
        
        # Decrypt
        k_final = alice_derive_final_key(k_pub, k_priv, len(ciphertext))
        decrypted = alice_decrypt(ciphertext, k_final)
        
        self.assertEqual(decrypted, plaintext)
        
    def test_decrypt_now_or_never(self):
        server = Server()
        t_start = 1
        t_end = 5
        
        # Encrypt
        result = server.encrypt_for_alice(b"msg", t_start, t_end)
        
        # Alice work
        history = alice_compute_public_history(result["public_seed"], result["public_salt"], t_end)
        checksum = alice_compute_checksum(history, t_start, t_end)
        
        # First release
        keys1 = server.verify_checksum_and_release_private_key_piece(checksum, t_start, t_end)
        
        # Second release (same window, server hasn't moved past)
        keys2 = server.verify_checksum_and_release_private_key_piece(checksum, t_start, t_end)
        self.assertEqual(keys1["k_private"], keys2["k_private"])
        
        # Move server forward
        t_start_new = 6
        t_end_new = 10
        history_new = alice_compute_public_history(result["public_seed"], result["public_salt"], t_end_new)
        checksum_new = alice_compute_checksum(history_new, t_start_new, t_end_new)
        
        server.verify_checksum_and_release_private_key_piece(checksum_new, t_start_new, t_end_new)
        
        # Ask for old window
        # Server returns H(S_current) which is H(S_10), not H(S_5)
        keys3 = server.verify_checksum_and_release_private_key_piece(checksum, t_start, t_end)
        self.assertNotEqual(keys3["k_private"], keys1["k_private"])

if __name__ == "__main__":
    unittest.main()
