import unittest
import os
from src.core import sha256, evolve_public_chain, derive_public_key_piece
from src.server import Server
from src.alice import alice_derive_final_key, alice_decrypt

class TestTimeEvolvingCrypto(unittest.TestCase):
    def setUp(self):
        self.server = Server()
        self.plaintext = b"Secret Message"
        self.t_start = 10
        self.t_end = 15

    def test_core_determinism(self):
        """Verify that hash chain evolution is deterministic."""
        seed = b"seed"
        salt = b"salt"
        chain1 = evolve_public_chain(seed, salt, 5)
        chain2 = evolve_public_chain(seed, salt, 5)
        self.assertEqual(chain1, chain2)

    def test_successful_flow(self):
        """Verify the happy path: Encrypt -> Verify -> Decrypt."""
        # 1. Encrypt
        enc_data = self.server.encrypt_for_alice(self.plaintext, self.t_start, self.t_end)
        
        # 2. Alice computes checksum (simulated)
        # We need to ensure server has history up to t_end for the test to work 
        # (encrypt_for_alice does this, but let's be explicit about what Alice does)
        # Alice would compute chain herself.
        alice_chain = evolve_public_chain(enc_data['public_seed'], enc_data['public_salt'], self.t_end)
        checksum = derive_public_key_piece(alice_chain, self.t_start, self.t_end)
        
        # 3. Verify and Release
        keys = self.server.verify_checksum_and_release_private_key_piece(checksum, self.t_start, self.t_end)
        
        # 4. Decrypt
        k_final = alice_derive_final_key(keys['k_public'], keys['k_private'])
        decrypted = alice_decrypt(enc_data['ciphertext'], k_final, enc_data['nonce'])
        
        self.assertEqual(decrypted, self.plaintext)

    def test_forward_secrecy_burn(self):
        """Verify that the server state advances and old keys are lost."""
        # 1. Snapshot state at t=0
        initial_state = self.server.private_state
        
        # 2. Encrypt for t=10
        enc_data = self.server.encrypt_for_alice(self.plaintext, 10, 10)
        
        # 3. Release keys (advances server to t=10)
        # We need the checksum first
        alice_chain = evolve_public_chain(enc_data['public_seed'], enc_data['public_salt'], 10)
        checksum = derive_public_key_piece(alice_chain, 10, 10)
        
        self.server.verify_checksum_and_release_private_key_piece(checksum, 10, 10)
        
        # 4. Verify server state has changed
        self.assertNotEqual(self.server.private_state, initial_state)
        self.assertEqual(self.server.current_t, 10) # It advances TO the target. 
        # Let's check implementation: advance_private_state_to(t_end) sets current_t to t_end.
        # Wait, looking at server.py:
        # while self.current_t < target_t: ... self.current_t += 1
        # So if target is 10, it stops at 10.
        
        # 5. Verify we cannot go back
        # Try to encrypt for t=5 (which is < 10)
        with self.assertRaises(ValueError):
            self.server.encrypt_for_alice(b"Fail", 5, 5)

    def test_late_arrival(self):
        """Verify that if Alice arrives late, she cannot get the key."""
        # Encrypt for t=10
        enc_data = self.server.encrypt_for_alice(self.plaintext, 10, 10)
        
        # Manually advance server to t=20 (simulating time passing or other decryptions)
        self.server.advance_private_state_to(20)
        
        # Now Alice tries to verify for t=10
        alice_chain = evolve_public_chain(enc_data['public_seed'], enc_data['public_salt'], 10)
        checksum = derive_public_key_piece(alice_chain, 10, 10)
        
        # This logic depends on implementation. 
        # Does verify_checksum check if t_end < current_t?
        # Let's check server.py behavior.
        # advance_private_state_to(t_end) will do nothing if current_t > t_end.
        # But verify_checksum_and_release... calls advance_private_state_to.
        # Then it calculates k_private = sha256(self.private_state).
        # If self.private_state is at t=20, and we ask for t=10...
        # The server will return H(S_20).
        # But the key for t=10 was H(S_10).
        # So the keys should NOT match.
        
        keys = self.server.verify_checksum_and_release_private_key_piece(checksum, 10, 10)
        k_private_late = keys['k_private']
        
        # Calculate what the key SHOULD have been (we need a fresh server to know)
        fresh_server = Server(
            public_seed=self.server.public_seed, 
            public_salt=self.server.public_salt, 
            server_secret=self.server.server_secret
        )
        # Inject the original private state (we can't easily get S_0 from the modified server, 
        # so this test setup is tricky without saving S_0. 
        # But we can just check if decryption fails.)
        
        k_final = alice_derive_final_key(keys['k_public'], k_private_late)
        
        # Decryption should fail (garbage output or MAC check fail)
        # AES-GCM raises InvalidTag if key is wrong.
        from cryptography.exceptions import InvalidTag
        with self.assertRaises(InvalidTag):
            alice_decrypt(enc_data['ciphertext'], k_final, enc_data['nonce'])

if __name__ == '__main__':
    unittest.main()
