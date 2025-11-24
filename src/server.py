import os
import struct
import hmac
import sqlite3
from .core import sha256, hkdf, derive_public_key_piece, encrypt_aes_gcm, decrypt_aes_gcm

DB_PATH = "server_state.db"

class Server:
    MAX_FUTURE_TICKS = 100

    def __init__(self, public_seed=None, public_salt=None, server_secret=None):
        self._init_db()
        
        # Get Master Key for DB encryption
        self.master_key = os.environ.get('SERVER_MASTER_KEY')
        if not self.master_key:
            print("WARNING: SERVER_MASTER_KEY not set. Using insecure default for demo.")
            self.master_key = b"insecure_default_master_key_32b"
        else:
            # Ensure it's bytes
            if isinstance(self.master_key, str):
                self.master_key = self.master_key.encode()
        
        # Ensure key is exactly 32 bytes for AES-256
        self.master_key = sha256(self.master_key)

        state = self._load_state()
        if state:
            print("Loading persisted server state...")
            self.public_seed = state['public_seed']
            self.public_salt = state['public_salt']
            self.server_secret = state['server_secret']
            self.private_state = state['private_state']
            self.current_t = state['current_t']
        else:
            print("Initializing new server state...")
            self.public_seed = public_seed or os.urandom(32)
            self.public_salt = public_salt or os.urandom(32)
            self.server_secret = server_secret or os.urandom(32)
            self.private_state = os.urandom(32) # S_0
            self.current_t = 0
            self._save_state()
        
        # Cache public history. Start with X_0.
        self.public_history = [self.public_seed]
        # Re-evolve history if we loaded from DB
        if self.current_t > 0:
            self._ensure_public_history_up_to(self.current_t)

    def refresh_state(self):
        """Reloads the current state from the database."""
        state = self._load_state()
        if state:
            # Check if seed or salt changed (e.g. if Ticker reset the DB or won a race)
            if state['public_seed'] != self.public_seed or state['public_salt'] != self.public_salt:
                print("DEBUG: Public seed/salt changed in DB. Resetting local history.")
                self.public_seed = state['public_seed']
                self.public_salt = state['public_salt']
                self.public_history = [self.public_seed] # Reset history

            self.server_secret = state['server_secret']
            self.private_state = state['private_state']
            self.current_t = state['current_t']
            # Also ensure history is up to date with the new time
            self._ensure_public_history_up_to(self.current_t)

    def _encrypt_blob(self, data: bytes) -> bytes:
        """Encrypts a blob using the master key."""
        nonce, ciphertext = encrypt_aes_gcm(self.master_key, data)
        return nonce + ciphertext

    def _decrypt_blob(self, blob: bytes) -> bytes:
        """Decrypts a blob using the master key."""
        nonce = blob[:12]
        ciphertext = blob[12:]
        return decrypt_aes_gcm(self.master_key, nonce, ciphertext)

    def _init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS server_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    public_seed BLOB NOT NULL,
                    public_salt BLOB NOT NULL,
                    server_secret BLOB NOT NULL,
                    private_state BLOB NOT NULL,
                    current_t INTEGER NOT NULL
                )
            """)

    def _load_state(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("SELECT public_seed, public_salt, server_secret, private_state, current_t FROM server_state WHERE id = 1")
            row = cursor.fetchone()
            if row:
                try:
                    return {
                        'public_seed': row[0],
                        'public_salt': row[1],
                        'server_secret': self._decrypt_blob(row[2]),
                        'private_state': self._decrypt_blob(row[3]),
                        'current_t': row[4]
                    }
                except Exception as e:
                    print(f"CRITICAL: Failed to decrypt server state. Master key mismatch? Error: {e}")
                    return None
            return None

    def _save_state(self):
        with sqlite3.connect(DB_PATH) as conn:
            # Encrypt sensitive fields
            enc_secret = self._encrypt_blob(self.server_secret)
            enc_private = self._encrypt_blob(self.private_state)
            
            conn.execute("""
                INSERT OR REPLACE INTO server_state (id, public_seed, public_salt, server_secret, private_state, current_t)
                VALUES (1, ?, ?, ?, ?, ?)
            """, (self.public_seed, self.public_salt, enc_secret, enc_private, self.current_t))

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

    def _ratchet_secret(self, current_secret):
        """
        Ratchets the server secret forward using HKDF.
        Secret_{t+1} = HKDF(Secret_t, salt="ratchet", info="server_secret_ratchet")
        """
        return hkdf(current_secret, 32, salt=b"ratchet", info=b"server_secret_ratchet")

    def advance_private_state_to(self, target_t):
        """
        Advances the private state S to S_{target_t}.
        S_{t+1} = H( S_t || X_t || server_secret || t )
        Also ratchets the server_secret: Secret_{t+1} = Ratchet(Secret_t)
        """
        self._ensure_public_history_up_to(target_t)
        
        while self.current_t < target_t:
            # We are at S_{current_t}. We want S_{current_t + 1}.
            # Formula uses S_t, X_t, server_secret, t.
            # So to get S_{t+1}, we use t = current_t.
            
            t = self.current_t
            x_t = self.public_history[t]
            t_bytes = struct.pack(">Q", t)
            
            # Domain Separation: EVOLVE context
            msg = b"EVOLVE" + x_t + self.server_secret + t_bytes
            self.private_state = hmac.new(self.private_state, msg, "sha256").digest()
            
            # RATCHET THE SERVER SECRET
            self.server_secret = self._ratchet_secret(self.server_secret)
            
            self.current_t += 1
            
        # Persist the new state
        self._save_state()

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
        temp_secret = self.server_secret
        temp_t = self.current_t
        
        # Simulate advance
        while temp_t < t_end:
            x_t = self.public_history[temp_t]
            t_bytes = struct.pack(">Q", temp_t)
            msg = b"EVOLVE" + x_t + temp_secret + t_bytes
            temp_state = hmac.new(temp_state, msg, "sha256").digest()
            
            # Simulate Ratchet
            temp_secret = self._ratchet_secret(temp_secret)
            
            temp_t += 1
            
        # Now temp_state is S_{t_end}.
        # Domain Separation: RELEASE context
        k_private = hmac.new(temp_state, b"RELEASE", "sha256").digest()
        
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
        # We allow t_end == self.current_t (the "Now"), but reject if current_t > t_end (the "Past").
        if t_end < self.current_t:
            raise ValueError(f"Window expired! Server is at t={self.current_t}, but you requested keys for t={t_end}. The keys are gone.")
            
        if t_end > self.current_t:
            raise ValueError(f"Too early! Server is at t={self.current_t}, but you requested keys for t={t_end}. Please wait.")

        # 2. Advance private state to t_end
        self.advance_private_state_to(t_end)
        
        # 3. Capture the key for t_end
        # Domain Separation: RELEASE context
        k_private = hmac.new(self.private_state, b"RELEASE", "sha256").digest()
        
        # 4. THE BURN: Advance to t_end + 1
        # This enforces "One-Shot". Once we give you the key for t_end, 
        # we immediately move to t_end + 1 so nobody else can get it.
        self.advance_private_state_to(t_end + 1)
        
        return {
            "k_public": expected_k_public,
            "k_private": k_private
        }
