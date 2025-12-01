# Version 3: Client-Side Key Wrapping Implementation Plan

## Objective
Migrate from Server-Side Data Encryption to Client-Side Data Encryption ("Key Wrapping").
Alice (Client) encrypts the payload locally. The Server only encrypts (wraps) the ephemeral data key.

## Architecture Changes
1.  **Client (Alice)**:
    *   Generates a random 256-bit AES key (`DataKey`).
    *   Encrypts the user's message using `DataKey` (AES-GCM).
    *   Sends *only* the `DataKey` to the Server.
    *   Displays the locally generated `DataCiphertext` and the returned `WrappedKey`.
2.  **Server**:
    *   New endpoint (or updated `/encrypt`): Accepts a key (small payload), encrypts it with the current Time-Lock Key.
    *   No longer sees the actual message content.

## Detailed Steps

### Phase 1: Setup & Branching
- [x] Create new branch `v3` from `v2` (or `main` if `v2` is merged).
- [x] Verify environment is clean and tests pass before starting.

### Phase 2: Client-Side Cryptography (JavaScript)
- [x] **Implement `generateKey()`**: Use `window.crypto.subtle.generateKey` to create a random AES-GCM key.
- [x] **Implement `encryptData(key, data)`**: Use `window.crypto.subtle.encrypt` to encrypt the user's text.
    *   *Problem*: Encoding. *Solution*: Use `TextEncoder` for string->bytes.
    *   *Problem*: IV handling. *Solution*: Generate random 12-byte IV. Return `{ ciphertext, iv }`.
- [x] **Implement `exportKey(key)`**: Export the raw key to a format suitable for sending to the server (e.g., Base64 or Hex string).
    *   *Problem*: Server expects text? *Solution*: Base64 encode the exported key bytes.

### Phase 3: Server-Side API Updates (Python)
- [x] **Update `app.py`**: Modify `/encrypt` (or create `/wrap_key`) to handle the key payload.
    *   *Note*: The server logic might not need deep changes if it just treats the input string as data to encrypt. However, semantically it's now a key.
    *   *Validation*: Ensure the payload size is small (it should be just a key, e.g., 32 bytes encoded). Reject large payloads to enforce the pattern?
- [x] **Update `server.py`**: Ensure `encrypt` method handles the data correctly. (Likely no change needed in core logic, just usage).

### Phase 4: Frontend Integration
- [x] **Update `script.js` Logic**:
    1.  User clicks "Encrypt".
    2.  JS generates `DataKey`.
    3.  JS encrypts Message -> `DataCiphertext`.
    4.  JS sends `DataKey` to Server.
    5.  Server returns `WrappedKey`.
    6.  UI displays:
        *   `Data Ciphertext` (Hex/Base64)
        *   `Wrapped Key` (Hex/Base64)
        *   `IV` (for Data)
        *   `Key ID` / `Timestamp`
- [x] **Update `index.html`**: Add fields to display the split between Data Ciphertext and Wrapped Key.

### Phase 5: Testing & Verification
- [x] **Unit Test JS**: Hard to unit test JS in this environment, but we can manual test.
- [x] **Integration Test**: Verify the full flow.
- [ ] **Security Check**: Verify the server logs (if any) do not show the message text.
- [ ] **Verify Decryption (Conceptual)**: Ensure we have a plan for how Bob would decrypt (even if not fully implemented in UI yet, the crypto must be reversible).
    *   Bob needs: `WrappedKey`, `DataCiphertext`, `DataIV`.
    *   Bob sends `WrappedKey` to Server -> gets `DataKey`.
    *   Bob uses `DataKey` + `DataIV` to decrypt `DataCiphertext`.

## Potential Problems & Solutions
1.  **Problem**: `window.crypto` is only available in Secure Contexts (HTTPS or localhost).
    *   **Solution**: We are running on localhost (http://127.0.0.1:5000), which is considered secure. If deployed, must use HTTPS.
2.  **Problem**: Data format mismatch between JS `ArrayBuffer` and Python `bytes`.
    *   **Solution**: Use standard Base64 helpers on both sides.
3.  **Problem**: User modifies the "Key" before sending?
    *   **Solution**: The client code controls the flow. If the user intercepts the request, they are just asking the server to encrypt arbitrary data. This is allowed (it's a public oracle).
4.  **Problem**: "Harvest Now, Decrypt Later" on the Key transmission.
    *   **Solution**: Acknowledge limitation. This step reduces the attack surface (Server doesn't see data), but the Key is still in transit. Future work: QKD or Pre-Shared Keys.
