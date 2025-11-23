Time-Evolving Ephemeral Decryption Protocol
Technical Specification & Security Analysis

1. Overview
The Time-Evolving Ephemeral Decryption Protocol is a time-based encryption scheme designed to enforce Perfect Forward Secrecy and mitigate "Harvest Now, Decrypt Later" (HNDL) attacks. Unlike traditional Public Key Infrastructure (PKI) where private keys are static, this protocol utilizes a rapidly evolving server state to ensure that decryption keys for past time windows are cryptographically erased and unrecoverable.

2. Cryptographic Primitives
The system relies exclusively on symmetric cryptography and hash functions, avoiding asymmetric primitives (RSA, ECC) vulnerable to Shor's algorithm.
Encryption: AES-256-GCM (Authenticated Encryption).
State Evolution: SHA-256 (One-way Hash Function).
Key Derivation: HKDF (HMAC-based Key Derivation Function).

3. Protocol Mechanics

A. Server State (The "Clock")
The server maintains a private internal state S_t that evolves discretely over time t.
S_{t+1} = SHA256(S_t || salt)
Crucially, this evolution is one-way. Given S_{t+1}, it is computationally infeasible to recover S_t. This provides the forward-secure property: the future does not remember the past.

B. Encryption (Time-Locking)
To encrypt a message for a validity window [t_start, t_end], the sender (or server) derives a unique ephemeral key K_final based on the server's future state at t_end.
1. Public Key Piece (K_pub): Derived from the public hash chain (Client computes this).
2. Private Key Piece (K_priv): Derived from the server's private state at t_end.
3. Final Key: K_final = HKDF(K_pub || K_priv).

The ciphertext is effectively "locked" until the server reaches t_end.

C. Decryption & Key Destruction
1. Client Proof: The client computes the public hash chain from t_start to t_end and presents a checksum (proof of work/time).
2. Verification: The server verifies the checksum.
3. State Advancement (The "Burn"): The server must advance its internal private state to t_end to generate K_priv.
S_current -> ... -> S_{t_end}
4. Release: The server returns K_priv to the client.
5. Irreversibility: The server overwrites its memory with S_{t_end}. All states S_0 ... S_{t_end}-1 are destroyed. Any ciphertext encrypted for a time t < t_end that has not yet been decrypted is now permanently undecryptable.

4. Security Properties & Use Cases

4.1 Security Scenario: The Compromised Endpoint
Consider an attacker who gains full access to a user's machine (or the server) at time T.
*   **Standard Encryption:** The attacker finds 1,000 encrypted files from the past year and the private key. They decrypt *everything*. Total history compromise.
*   **Ephemeral One-Shot:** The attacker finds 1,000 encrypted files. They try to decrypt them.
    *   Files 1-999 (Past): The server has already advanced past their windows. The keys are gone. Decryption fails.
    *   File 1,000 (Current): If it hasn't been decrypted yet, the attacker *can* decrypt this one file.
    *   **Result:** The attacker gets *only* the current active file, not the entire history. The damage is contained to the "now".

4.2 Data at Rest Protection
While HNDL is often discussed in the context of "Data in Transit" (intercepting network traffic), this protocol primarily secures "Data at Rest." It allows ciphertext to be stored on a disk where it automatically becomes unreadable after the time window expires, even if the file itself is never deleted.

4.3 Time-Gated Access Control
The protocol enables precise time-locking. A file can be encrypted to be accessible only within a specific future window (e.g., "Tick 100 to Tick 105"). Before Tick 100, the key does not yet exist. After Tick 105, the key is destroyed.

5. Limitations
One-Shot Decryption: Decryption is a destructive event. To release the key for a specific window (e.g., Tick 100), the server must fast-forward its state to that tick. This action irreversibly burns all previous keys. Therefore, a message can be decrypted exactly once. If User A decrypts it, the server moves forward, and User B cannot decrypt it subsequently.
Interactive Requirement: Decryption requires an online, active server.
Strict Time Windows: If a legitimate client misses the decryption window (server advances past t_end), the data is lost.
Serial Dependency: The server is a single point of state. Distributed implementations require synchronized state management (e.g., Raft consensus) to maintain the one-way property.
