import unittest
import os
from src.server import Server
from src.alice import alice_compute_public_history, alice_compute_checksum, alice_derive_final_key, alice_decrypt

class TestProtocol(unittest.TestCase):
    def setUp(self):
        if os.path.exists("server_state.db"):
            os.remove("server_state.db")

    def tearDown(self):
        if os.path.exists("server_state.db"):
            os.remove("server_state.db")

    def test_full_flow(self):
        server = Server()
        plaintext = b"secret message"
        t_start = 1
        t_end = 5
        
        # Encrypt
        request_nonce = os.urandom(8).hex()
        result = server.encrypt_for_alice(plaintext, t_start, t_end, request_nonce)
        ciphertext = result["ciphertext"]
        nonce = result["nonce"]
        pub_seed = result["public_seed"]
        pub_salt = result["public_salt"]
        
        # Alice work
        history = alice_compute_public_history(pub_seed, pub_salt, t_end)
        checksum = alice_compute_checksum(history, t_start, t_end)
        
        # Advance server time to t_end so keys can be released
        server.advance_private_state_to(t_end)
        
        # Key release
        request_nonce_verify = os.urandom(8).hex()
        keys = server.verify_checksum_and_release_private_key_piece(checksum, t_start, t_end, request_nonce_verify)
        k_pub = keys["k_public"]
        k_priv = keys["k_private"]
        
        # Decrypt
        k_final = alice_derive_final_key(k_pub, k_priv, 32)
        decrypted = alice_decrypt(ciphertext, k_final, nonce)
        
        self.assertEqual(decrypted, plaintext)
        
    def test_decrypt_now_or_never(self):
        server = Server()
        t_start = 1
        t_end = 5
        
        # Encrypt
        request_nonce = os.urandom(8).hex()
        result = server.encrypt_for_alice(b"msg", t_start, t_end, request_nonce)
        
        # Alice work
        history = alice_compute_public_history(result["public_seed"], result["public_salt"], t_end)
        checksum = alice_compute_checksum(history, t_start, t_end)
        
        # Advance server time
        server.advance_private_state_to(t_end)
        
        # First release
        request_nonce_verify = os.urandom(8).hex()
        _ = server.verify_checksum_and_release_private_key_piece(checksum, t_start, t_end, request_nonce_verify)
        
        # Second release (same window, server hasn't moved past)
        # The server enforces one-shot, so this should fail immediately
        # Even with a new nonce, the server state has advanced past the window (BURN EVENT)
        request_nonce_verify2 = os.urandom(8).hex()
        with self.assertRaises(ValueError):
            server.verify_checksum_and_release_private_key_piece(checksum, t_start, t_end, request_nonce_verify2)
        
        # Move server forward
        t_start_new = 6
        t_end_new = 10
        history_new = alice_compute_public_history(result["public_seed"], result["public_salt"], t_end_new)
        checksum_new = alice_compute_checksum(history_new, t_start_new, t_end_new)
        
        server.advance_private_state_to(t_end_new)
        
        request_nonce_verify3 = os.urandom(8).hex()
        server.verify_checksum_and_release_private_key_piece(checksum_new, t_start_new, t_end_new, request_nonce_verify3)
        
        # Ask for old window
        # Server should reject this request as the window has expired
        request_nonce_verify4 = os.urandom(8).hex()
        with self.assertRaises(ValueError):
            server.verify_checksum_and_release_private_key_piece(checksum, t_start, t_end, request_nonce_verify4)

if __name__ == "__main__":
    unittest.main()
