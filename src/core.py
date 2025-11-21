import hashlib
import hmac
import struct

def sha256(data: bytes) -> bytes:
    """Computes SHA-256 hash of the input data."""
    return hashlib.sha256(data).digest()

def xor_bytes(a: bytes, b: bytes) -> bytes:
    """XORs two byte strings of equal length."""
    if len(a) != len(b):
        raise ValueError("Byte strings must be equal length")
    return bytes(x ^ y for x, y in zip(a, b))

def hkdf_extract(salt: bytes, input_key_material: bytes) -> bytes:
    if salt is None or len(salt) == 0:
        salt = bytes([0] * hashlib.sha256().digest_size)
    return hmac.new(salt, input_key_material, hashlib.sha256).digest()

def hkdf_expand(pseudo_random_key: bytes, info: bytes, length: int) -> bytes:
    if info is None:
        info = b""
    t = b""
    okm = b""
    n = 0
    while len(okm) < length:
        n += 1
        t = hmac.new(pseudo_random_key, t + info + bytes([n]), hashlib.sha256).digest()
        okm += t
    return okm[:length]

def hkdf(ikm: bytes, length: int, salt: bytes = None, info: bytes = None) -> bytes:
    """
    HMAC-based Extract-and-Expand Key Derivation Function (HKDF).
    Implemented using standard library hmac and hashlib.
    """
    prk = hkdf_extract(salt, ikm)
    return hkdf_expand(prk, info, length)

def evolve_public_chain(x0: bytes, salt: bytes, steps: int) -> list[bytes]:
    """
    Evolves the public non-Markovian hash chain.
    
    X_{t+1} = H( X_t || X_{t-1} || salt_public || t )
    
    Args:
        x0: The initial public seed (X_0).
        salt: The public salt.
        steps: Number of steps to evolve.
        
    Returns:
        A list of bytes containing [X_0, X_1, ..., X_steps].
    """
    history = [x0]
    
    # X_{-1} is defined as 32 bytes of zeros for the first step
    prev_x = bytes(32)
    
    for t in range(steps):
        # Current X_t is the last element in history
        current_x = history[-1]
        
        # t is the step index, starting from 0.
        # We are computing X_{t+1}.
        # We use 8 bytes (64-bit big-endian) for t.
        t_bytes = struct.pack(">Q", t)
        
        # Input: X_t || X_{t-1} || salt || t
        data = current_x + prev_x + salt + t_bytes
        next_x = sha256(data)
        
        history.append(next_x)
        prev_x = current_x
        
    return history

def derive_public_key_piece(history: list[bytes], t_start: int, t_end: int) -> bytes:
    """
    Derives a public key piece from a window of the public chain history.
    
    K_public = H( X_{t_start} || X_{t_start+1} || ... || X_{t_end} )
    
    Args:
        history: The full public chain history.
        t_start: Start index (inclusive).
        t_end: End index (inclusive).
        
    Returns:
        The derived public key piece (32 bytes).
    """
    if t_start < 0 or t_end >= len(history) or t_start > t_end:
        raise ValueError("Invalid time window")
        
    # Concatenate all X_t in the window
    window_data = b"".join(history[t_start : t_end + 1])
    return sha256(window_data)
