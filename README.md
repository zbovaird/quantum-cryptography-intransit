# Time-Evolving Ephemeral Decryption Protocol (PoC)

This is a research prototype (Proof of Concept) for a new encryption model.

## Concept
- **Public Chain**: Sequential work required by the client.
- **Private Chain**: Server-side evolving state that never repeats.
- **Decrypt Now or Never**: Decryption requires a private key piece that is only available ephemerally from the server.

## Usage (Docker - Recommended)
1. Run the server and client demo:
   ```bash
   docker-compose up
   ```
   This will start the server and run the client demo script against it.

2. Run tests:
   ```bash
   docker-compose run tests
   ```

## Usage (Local)
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   (or use `pyproject.toml`)

2. Run the demo:
   ```bash
   python -m src.demo
   ```

## Disclaimer
**NOT PRODUCTION CRYPTO.** This is for research and validation of the protocol flow only.
