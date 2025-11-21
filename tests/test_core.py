import unittest
import os
from src.core import sha256, xor_bytes, hkdf, evolve_public_chain, derive_public_key_piece

class TestCore(unittest.TestCase):
    def test_sha256(self):
        data = b"hello world"
        expected = b"\xb9\x4d\x27\xb9\x93\x4d\x3e\x08\xa5\x2e\x52\xd7\xda\x7d\xab\xfa\xc4\x84\xfe\x37\x95\x32\x39\x26\xaf\x88\x36\x88\xa5\xee\x52\xfd"
        self.assertEqual(sha256(data), expected)

    def test_xor_bytes(self):
        a = b"\x00\xFF\xAA"
        b = b"\xFF\x00\x55"
        expected = b"\xFF\xFF\xFF"
        self.assertEqual(xor_bytes(a, b), expected)
        
        with self.assertRaises(ValueError):
            xor_bytes(b"1", b"12")

    def test_hkdf(self):
        ikm = b"input key material"
        salt = b"salt"
        info = b"info"
        length = 32
        k1 = hkdf(ikm, length, salt, info)
        k2 = hkdf(ikm, length, salt, info)
        self.assertEqual(k1, k2)
        self.assertEqual(len(k1), length)

    def test_evolve_public_chain_deterministic(self):
        x0 = os.urandom(32)
        salt = os.urandom(32)
        steps = 10
        
        chain1 = evolve_public_chain(x0, salt, steps)
        chain2 = evolve_public_chain(x0, salt, steps)
        
        self.assertEqual(len(chain1), steps + 1) # X_0 ... X_steps
        self.assertEqual(chain1, chain2)
        
    def test_derive_public_key_piece(self):
        x0 = b"\x00" * 32
        salt = b"\x00" * 32
        steps = 5
        chain = evolve_public_chain(x0, salt, steps)
        
        # Test valid window
        k_pub = derive_public_key_piece(chain, 1, 3)
        self.assertEqual(len(k_pub), 32)
        
        # Test invalid window
        with self.assertRaises(ValueError):
            derive_public_key_piece(chain, 3, 1)
        with self.assertRaises(ValueError):
            derive_public_key_piece(chain, 0, 10)

if __name__ == "__main__":
    unittest.main()
