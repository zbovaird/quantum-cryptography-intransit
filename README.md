# Time-Evolving Ephemeral Decryption Protocol (PoC) - v3

This is a research prototype (Proof of Concept) for a new encryption model where data can only be decrypted within a specific time window.

## v3 Architecture: Key Wrapping & Timekeeper

Version 3 introduces a robust "Key Wrapping" architecture and an automated Timekeeper.

### Core Concepts
1.  **Client-Side Encryption**: Data is encrypted locally in the browser (or client) using AES-GCM. The data itself is never sent to the server.
2.  **Key Wrapping**: The AES key is "wrapped" (encrypted) using a server-derived ephemeral key. This wrapped key is stored on the server.
3.  **Time-Lock**: The server's key evolves every second (via a hash chain). The wrapped key can only be unwrapped if the server is at the exact specific tick `t` when the key was generated.
4.  **Timekeeper**: A background thread on the server automatically advances the server tick every second, enforcing real-time expiration.

### Workflow
1.  **Encrypt**: Client generates a random AES key, encrypts data, and sends the key to the server. Server wraps the key with its current state `S_t` and returns the wrapped key + metadata (nonce, tick `t`).
2.  **Wait**: The server state evolves (`t` -> `t+1` -> ...).
3.  **Decrypt**: Client requests decryption.
    *   If `current_tick == target_tick`: Server unwraps the key and returns it. Client decrypts data.
    *   If `current_tick != target_tick`: Server cannot derive the correct unwrapping key. Decryption fails permanently.

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
