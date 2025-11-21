Non-Markovian Ephemeral Decryption Protocol – PLAN
0. High-Level Goal

Build a proof-of-concept (PoC) for a new encryption model where:

Decryption requires live server cooperation.

The server maintains a private, evolving state that never repeats and never rewinds.

The client must perform sequential public work (non-Markovian hash chain) to prove “time” has passed.

Even if an attacker records all traffic and has a quantum computer, captured ciphertext cannot be decrypted later without intercepting an ephemeral private key piece in transit.

This PoC is not production crypto. It’s a research prototype to validate:

The protocol flow (Alice ↔ Server).

The separation between public chain and private chain.

The “decrypt now or never” property.

1. Tech Stack and Project Structure
1.1 Language / Runtime

Python 3.10+

Python standard library plus one crypto library (hashlib, hmac, os, and either cryptography or pyca/cryptography for AES-GCM)

1.2 Suggested Project Layout

nonmarkov-ephemeral-crypto/
PLAN.md
README.md
pyproject.toml (or requirements.txt)
src/
init.py
core.py
server.py
alice.py
demo.py
tests/
test_core.py
test_protocol.py

You can start with src/core.py, src/server.py, src/alice.py, and src/demo.py, then add tests.

2. Core Concepts to Implement
2.1 Public Non-Markovian Process F

Global public seed X0 (32 bytes)

Public salt salt_public (32 bytes)

Define a non-Markovian hash chain:

X_{t+1} = H( X_t || X_{t-1} || salt_public || t )

Can generalize to deeper history if desired.

Deliverables:

evolve_public_chain(x0, salt, steps)

derive_public_key_piece(history, t_start, t_end)

2.2 Private Server Process G

Private seed S0 (32 bytes)

Server secret server_secret (32 bytes)

Private evolution rule:

S_{t+1} = H( S_t || X_t || server_secret || t )

Only the server maintains S_t internally.

Deliverables:

Server class with encrypted message generation and checksum verification.

3. Stepwise Implementation Plan
Step 1 – Core Hash Utilities (src/core.py)

Tasks:

Implement sha256, hkdf (simple version), xor_bytes.

Optionally integrate AES-GCM for real symmetric encryption.

Acceptance criteria:

Functions produce deterministic test outputs.

No side effects.

Step 2 – Public Chain F (src/core.py)

Tasks:

Implement evolve_public_chain(x0, salt, steps).

Implement derive_public_key_piece(history, t_start, t_end).

Add simple tests verifying deterministic behavior.

Step 3 – Server Class and Private Chain G (src/server.py)

Design properties:

Stores public_seed, public_salt.

Stores private_state = S_t.

Stores server_secret.

Caches public history for self-use.

Methods:

_ensure_public_history_up_to(t): build public chain X0..Xt.

advance_private_state_to(t): run S{k+1} = H(S_k || X_k || server_secret || k).

encrypt_for_alice:

ensure public history up to t_end

compute K_public from public window

encrypt plaintext using K_public or a derived key

return: ciphertext, t_start, t_end, public_seed, public_salt, hash info

verify_checksum_and_release_private_key_piece:

recompute K_public internally

verify client checksum

advance private state to t_end

return: K_public and K_private = H(S_t_end)

Step 4 – Alice-Side Helpers (src/alice.py)

Implement:

alice_compute_public_history(public_seed, public_salt, steps)

alice_compute_checksum(history, t_start, t_end)

alice_derive_final_key(k_public, k_private, length)

alice_decrypt(ciphertext, k_final)

Step 5 – End-to-End Demo (src/demo.py)

Demo flow:

Create Server with random seeds/secrets.

Create plaintext.

Choose window [t_start, t_end], like 900–950.

Server.encrypt_for_alice → returns ciphertext + metadata.

Alice:

computes public chain up to t_end

computes checksum for the public window

Send checksum back to server:

server.verify_checksum_and_release_private_key_piece

server returns (K_public_server, K_private)

Alice recomputes K_public locally.

Alice derives K_final from both key parts.

Alice decrypts ciphertext and prints results.

Add a simulated attacker:

Observes ciphertext + metadata

Computes K_public from public chain

Never sees K_private

Attempt to decrypt → fails, proving “decrypt now or never.”

4. Hardening and Extensions (Optional)

After bare PoC:

Replace XOR encryption with AES-GCM:

AES-256-GCM using K_final as the key.

Add replay/session-binding fields:

session_id

nonce

timestamp

Bind these into key derivation so that even K_public and K_private depend on them.

Implement tracking so each window [t_start, t_end] can only be used once.

Add knobs for difficulty (longer public windows, deeper history dependence).

5. README Outline

Your README should include:

What this project is (research-only PoC).

What it is not (production-ready crypto).

How it works in three bullets:

Public hash chain enforces sequential work.

Private server hash chain evolves a hidden state.

Decryption requires combining public and private pieces, and the private piece exists only once.

Instructions for running:

pip install -r requirements.txt

python -m src.demo

Future directions:

Formalizing F/G with Barandes’ indivisible stochastic processes.

Security analysis for quantum adversaries (no oracle problem).

6. Stretch Goals

Write docs/protocol.md containing:

Message formats (M1: ciphertext+metadata, M2: checksum, M3: private key piece).

Threat model (MITM, replay, quantum attacker).

Build mini HTTP or gRPC service to show live interaction:

/encrypt

/submit_checksum

Write an attack simulation that records all network traffic and proves ciphertext cannot be decrypted without the private-state-derived key.

7. Implementation Order Checklist

core.py: hash utilities and F functions.

server.py: private state G, encryption, verify.

alice.py: public chain, checksum, key derivation, decrypt.

demo.py: end-to-end test, including simulated attacker.

Replace XOR → AES-GCM (optional).

Add tests and README.
