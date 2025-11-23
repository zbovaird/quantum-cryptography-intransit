import os
import struct
import hmac
from .core import sha256, hkdf, derive_public_key_piece, encrypt_aes_gcm

class Server:
    MAX_FUTURE_TICKS = 100

    def __init__(self, public_seed=None, public_salt=None, server_secret=None):
        self.public_seed = public_seed or os.urandom(32)
        self.public_salt = public_salt or os.urandom(32)
        self.server_secret = server_secret or os.urandom(32)
        
        self.private_state = os.urandom(32) # S_0
        self.current_t = 0
        
        # Cache public history. Start with X_0.
        self.public_history = [self.public_seed]

    def _ensure_public_history_up_to(self, t):
        """Ensures public_history contains X_0 ... X_t."""
        current_len = len(self.public_history)
        if t < current_len:
            return
        
        # Continue evolving from the last known state
        x_prev = self.public_history[-2] if current_len >= 2 else bytes(32)
        x_curr = self.public_history[-1]
        
        # We need to compute X_k for k from current_len to t (inclusive indices in history)
        # The loop in evolve_public_chain computes X_{t+1} given X_t.
        # Here, we want to compute X_{current_len}, X_{current_len+1}, ..., X_t.
        # The step index for computing X_{k+1} is k.
        # So to compute X_{current_len}, we use step index k = current_len - 1.
        
        for k in range(current_len - 1, t):
            # k is the step index.
            # We are computing X_{k+1}.
            t_bytes = struct.pack(">Q", k)
            data = x_curr + x_prev + self.public_salt + t_bytes
            x_next = sha256(data)
            self.public_history.append(x_next)
            x_prev = x_curr
            x_curr = x_next

    def advance_private_state_to(self, target_t):
        """
        Advances the private state S to S_{target_t}.
        S_{t+1} = H( S_t || X_t || server_secret || t )
        """
        self._ensure_public_history_up_to(target_t)
        
        while self.current_t < target_t:
            # We are at S_{current_t}. We want S_{current_t + 1}.
            # Formula uses S_t, X_t, server_secret, t.
            # So to get S_{t+1}, we use t = current_t.
            
            t = self.current_t
            x_t = self.public_history[t]
            t_bytes = struct.pack(">Q", t)
            
            data = self.private_state + x_t + self.server_secret + t_bytes
            self.private_state = sha256(data)
            self.current_t += 1

    def encrypt_for_alice(self, plaintext: bytes, t_start: int, t_end: int):
        """
        Encrypts a message for a specific time window.
        Does NOT advance the persistent private state.
        """
        if self.current_t > t_end:
            raise ValueError(f"Server already passed t_end (current: {self.current_t}, target: {t_end}). Cannot encrypt.")

        if t_end > self.current_t + self.MAX_FUTURE_TICKS:
            raise ValueError(f"Time window too far in the future. Max allowed is +{self.MAX_FUTURE_TICKS} ticks.")

        # 1. Ensure public history
        self._ensure_public_history_up_to(t_end)
        
        # 2. Compute K_public
        k_public = derive_public_key_piece(self.public_history, t_start, t_end)
        
        # 3. Compute K_private (future)
        # We need S_{t_end}.
        # We don't want to advance self.private_state yet.
        # So we simulate it.
        
        temp_state = self.private_state
        temp_t = self.current_t
        
        # Simulate advance
        while temp_t < t_end:
            x_t = self.public_history[temp_t]
            t_bytes = struct.pack(">Q", temp_t)
            data = temp_state + x_t + self.server_secret + t_bytes
            temp_state = sha256(data)
            temp_t += 1
            
        # Now temp_state is S_{t_end}.
        k_private = sha256(temp_state)
        
        # 4. Derive K_final
        # K_final = HKDF(K_public || K_private, length=32) for AES-GCM
        k_final = hkdf(k_public + k_private, 32, salt=b"encryption", info=b"aes_gcm_key")
        
        # 5. Encrypt (AES-GCM)
        nonce, ciphertext = encrypt_aes_gcm(k_final, plaintext)
        
        return {
            "ciphertext": ciphertext,
            "nonce": nonce,
            "t_start": t_start,
            "t_end": t_end,
            "public_seed": self.public_seed,
            "public_salt": self.public_salt
        }

    def verify_checksum_and_release_private_key_piece(self, checksum: bytes, t_start: int, t_end: int):
        """
        Verifies Alice's work and releases the private key piece.
        Advances the private state to t_end, making previous keys inaccessible.
        """
        if t_end > self.current_t + self.MAX_FUTURE_TICKS:
            raise ValueError(f"Time window too far in the future. Max allowed is +{self.MAX_FUTURE_TICKS} ticks.")

        self._ensure_public_history_up_to(t_end)
        expected_k_public = derive_public_key_piece(self.public_history, t_start, t_end)
        
        if not hmac.compare_digest(checksum, expected_k_public):
            raise ValueError("Invalid checksum")

        # 1.5 Check if window is already passed
        if t_end <= self.current_t:
            raise ValueError(f"Window expired! Server is at t={self.current_t}, but you requested keys for t={t_end}. The keys are gone.")
            
        # 2. Advance private state to t_end
        # This is the "point of no return".
        self.advance_private_state_to(t_end)
        
        # 3. Return keys
        # K_private = H(S_{t_end})
        k_private = sha256(self.private_state)
        
        return {
            "k_public": expected_k_public,
            "k_private": k_private
        }
