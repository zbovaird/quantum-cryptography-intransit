# Time-Evolving Ephemeral Decryption Protocol (PoC) - v3

This is a research prototype (Proof of Concept) for a new encryption model where data can only be decrypted within a specific time window.

## v3 Architecture: Key Wrapping & Timekeeper

Version 3 introduces a robust "Key Wrapping" architecture and an automated Timekeeper.

### Core Concepts
1.  **Client-Side Encryption**: Data is encrypted locally in the browser (or client) using AES-GCM. The data itself is never sent to the server.
2.  **Key Wrapping**: The AES key is "wrapped" (encrypted) using a server-derived ephemeral key. This wrapped key is stored on the server.
3.  **Time-Lock**: The server's key evolves every second (via a hash chain). The wrapped key can only be unwrapped if the server is at the exact specific tick `t` when the key was generated.
4.  **Timekeeper**: A background thread on the server automatically advances the server tick every second, enforcing real-time expiration.

### Protocol Sequence

#### 1. Encryption Phase (Alice)
*   **Key Generation:** Alice's client generates a random, one-time **Session Key** (e.g., AES-256).
*   **Local Encryption:** Alice uses this Session Key to encrypt her message locally.
    *   *Result:* **Data Ciphertext** (The encrypted message).
*   **Key Wrapping Request:** Alice sends *only* the **Session Key** to the Timekeeper Server.
*   **Time-Locking:** The Timekeeper receives the Session Key, encrypts it with the current ephemeral server key (at `Tick T`), and immediately discards the Session Key.
    *   *Result:* **Wrapped Key**.
*   **Package Delivery:** Alice sends the package to Bob (via any channel):
    *   `Data Ciphertext`
    *   `Wrapped Key`
    *   `Target Tick: T`

#### 2. The Waiting Game
*   The Timekeeper's state evolves (`T` -> `T+1` -> ...).
*   The key required to unwrap the **Wrapped Key** is only available at `Tick T`.
*   Once the server moves past `Tick T`, the key is destroyed forever (Forward Secrecy).

#### 3. Decryption Phase (Bob)
*   **The Clock Strikes:** Bob must attempt decryption while the Timekeeper is exactly at `Tick T`.
*   **Unwrap Request:** Bob sends the **Wrapped Key** to the Timekeeper.
*   **Verification:** The Timekeeper checks if `Current Tick == Target Tick`.
*   **Unwrapping:** If the time is right, the Timekeeper unwraps the key and returns the original **Session Key** to Bob.
*   **Final Decryption:** Bob uses the Session Key to decrypt the **Data Ciphertext** locally.

If Bob misses the window (even by a second), the Timekeeper cannot mathematically reconstruct the key, and the message is lost forever.

## Usage

### Prerequisites
- Python 3.9+
- Docker (optional)

### Local Setup
1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Run the Server**:
    ```bash
    python src/app.py
    ```
    The server will start on `http://localhost:5001`.
    *   The **Timekeeper** will automatically start ticking.

3.  **Web Interface**:
    Open `http://localhost:5001` in your browser.
    *   **Visualizer**: Watch the server state (Hash & Tick) evolve in real-time.
    *   **Demo**: Type a message, encrypt it, and try to decrypt it. You must hit "Decrypt" within the same 1-second window to succeed!

### Docker Setup
1.  Run the stack:
    ```bash
    docker-compose up --build
    ```
2.  Access the web interface at `http://localhost:5001`.

## Testing
Run the test suite to verify the protocol logic and timing mechanics:
```bash
python -m unittest discover tests
```

## Disclaimer
**NOT PRODUCTION CRYPTO.** This is for research and validation of the protocol flow only. Do not use for sensitive data.
