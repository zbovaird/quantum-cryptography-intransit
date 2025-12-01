import unittest
import json
import time
import threading
from src.app import app, server_instance
from src.alice import alice_compute_public_history, alice_compute_checksum, alice_derive_final_key, alice_decrypt
import binascii
import os

class TestV3API(unittest.TestCase):
    def setUp(self):
        app.testing = True
        self.app = app.test_client()
        # Reset server state for each test
        server_instance.__init__() 

    def test_full_flow_api(self):
        # 1. Encrypt
        plaintext_key = os.urandom(32).hex() # Simulating the Session Key
        t_start = server_instance.current_t + 2
        t_end = t_start + 2
        request_nonce = "11111111"
        
        response = self.app.post('/encrypt', json={
            "plaintext": plaintext_key,
            "t_start": t_start,
            "t_end": t_end,
            "request_nonce": request_nonce
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        ciphertext = binascii.unhexlify(data['ciphertext'])
        nonce = binascii.unhexlify(data['nonce'])
        pub_seed = binascii.unhexlify(data['public_seed'])
        pub_salt = binascii.unhexlify(data['public_salt'])
        
        # 2. Advance Time to t_end
        server_instance.advance_private_state_to(t_end)
        
        # 3. Compute Checksum (Client Side Simulation)
        history = alice_compute_public_history(pub_seed, pub_salt, t_end)
        checksum = alice_compute_checksum(history, t_start, t_end)
        checksum_hex = checksum.hex()
        
        # 4. Verify (The new client flow)
        verify_nonce = "22222222"
        response = self.app.post('/verify', json={
            "checksum": checksum_hex,
            "t_start": t_start,
            "t_end": t_end,
            "request_nonce": verify_nonce
        })
        
        self.assertEqual(response.status_code, 200)
        verify_data = response.get_json()
        
        k_public_hex = verify_data['k_public']
        k_private_hex = verify_data['k_private']
        
        self.assertEqual(k_public_hex, checksum_hex)
        
        # 5. Derive Final Key and Decrypt (Client Side Simulation)
        k_public = binascii.unhexlify(k_public_hex)
        k_private = binascii.unhexlify(k_private_hex)
        
        k_final = alice_derive_final_key(k_public, k_private)
        decrypted_key = alice_decrypt(ciphertext, k_final, nonce)
        
        self.assertEqual(decrypted_key.hex(), plaintext_key)

    def test_client_helper_removed(self):
        response = self.app.post('/client-helper', json={})
        self.assertEqual(response.status_code, 404)

if __name__ == '__main__':
    unittest.main()
