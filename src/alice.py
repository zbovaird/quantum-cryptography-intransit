from .core import evolve_public_chain, derive_public_key_piece, hkdf, decrypt_aes_gcm

def alice_compute_public_history(public_seed: bytes, public_salt: bytes, steps: int) -> list[bytes]:
    """
    Computes the public hash chain history.
    """
    return evolve_public_chain(public_seed, public_salt, steps)

def alice_compute_checksum(history: list[bytes], t_start: int, t_end: int) -> bytes:
    """
    Computes the checksum (K_public) for the given window.
    """
    return derive_public_key_piece(history, t_start, t_end)

def alice_derive_final_key(k_public: bytes, k_private: bytes, length: int = 32) -> bytes:
    """
    Derives the final decryption key from K_public and K_private.
    Length should be 32 for AES-256.
    """
    return hkdf(k_public + k_private, length, salt=b"encryption", info=b"aes_gcm_key")

def alice_decrypt(ciphertext: bytes, k_final: bytes, nonce: bytes) -> bytes:
    """
    Decrypts the ciphertext using the final key.
    """
    return decrypt_aes_gcm(k_final, nonce, ciphertext)
