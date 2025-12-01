from flask import Flask, request, jsonify, render_template
from src.server import Server
import binascii
import time
import threading

app = Flask(__name__)

# Initialize server
# In a real app, we'd need persistent storage or a singleton that doesn't reset on reload.
# For this PoC, a global variable is fine as long as we don't use multiple workers.
server_instance = Server()

def ticker_loop():
    """Background thread to advance server time every second."""
    print("Starting Timekeeper Ticker...")
    while True:
        time.sleep(1)
        try:
            # We must refresh state to get the latest t from DB (in case other processes moved it)
            server_instance.refresh_state()
            # Advance by 1 tick
            server_instance.advance_private_state_to(server_instance.current_t + 1)
            # print(f"TICK: {server_instance.current_t}") 
        except Exception as e:
            print(f"Ticker error: {e}")

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/status', methods=['GET'])
def status():
    server_instance.refresh_state()
    return jsonify({
        "current_t": server_instance.current_t,
        "public_history_len": len(server_instance.public_history)
    })

@app.route('/encrypt', methods=['POST'])
def encrypt():
    server_instance.refresh_state()
    data = request.json
    plaintext_hex = data.get('plaintext')
    t_start = data.get('t_start')
    t_end = data.get('t_end')
    
    if not all([plaintext_hex, t_start, t_end]):
        return jsonify({"error": "Missing parameters"}), 400
        
    if not isinstance(t_start, int) or not isinstance(t_end, int):
        return jsonify({"error": "t_start and t_end must be integers"}), 400
        
    request_nonce = data.get('request_nonce')
    if not request_nonce:
        return jsonify({"error": "Missing request_nonce"}), 400

    try:
        plaintext = binascii.unhexlify(plaintext_hex)
        result = server_instance.encrypt_for_alice(plaintext, t_start, t_end, request_nonce)
        
        # Convert bytes to hex for JSON response
        response = {
            "ciphertext": result["ciphertext"].hex(),
            "nonce": result["nonce"].hex(),
            "t_start": result["t_start"],
            "t_end": result["t_end"],
            "public_seed": result["public_seed"].hex(),
            "public_salt": result["public_salt"].hex(),
            "request_nonce": request_nonce
        }
        return jsonify(response)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/verify', methods=['POST'])
def verify():
    server_instance.refresh_state()
    data = request.json
    checksum_hex = data.get('checksum')
    t_start = data.get('t_start')
    t_end = data.get('t_end')
    
    if not all([checksum_hex, t_start, t_end]):
        return jsonify({"error": "Missing parameters"}), 400

    if not isinstance(t_start, int) or not isinstance(t_end, int):
        return jsonify({"error": "t_start and t_end must be integers"}), 400
        
    request_nonce = data.get('request_nonce')
    if not request_nonce:
        return jsonify({"error": "Missing request_nonce"}), 400

    try:
        checksum = binascii.unhexlify(checksum_hex)
        keys = server_instance.verify_checksum_and_release_private_key_piece(checksum, t_start, t_end, request_nonce)
        
        response = {
            "k_public": keys["k_public"].hex(),
            "k_private": keys["k_private"].hex()
        }
        return jsonify(response)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

from src.alice import alice_compute_public_history, alice_compute_checksum, alice_derive_final_key, alice_decrypt

@app.route('/client-helper', methods=['POST'])
def client_helper():
    """
    Helper endpoint for the web UI to simulate Alice's client-side work.
    Avoids re-implementing crypto in JS.
    """
    server_instance.refresh_state()
    data = request.json
    try:
        ciphertext = binascii.unhexlify(data["ciphertext"])
        nonce = binascii.unhexlify(data["nonce"])
        pub_seed = binascii.unhexlify(data["public_seed"])
        pub_salt = binascii.unhexlify(data["public_salt"])
        t_start = data["t_start"]
        t_end = data["t_end"]
        
        # 1. Compute Chain
        history = alice_compute_public_history(pub_seed, pub_salt, t_end)
        
        # 2. Compute Checksum
        checksum = alice_compute_checksum(history, t_start, t_end)
        
        # 3. Verify with Server
        # Client helper needs to generate a NEW nonce for the verification step, 
        # because the encryption nonce was already used!
        import os
        verify_nonce = os.urandom(8).hex()
        keys = server_instance.verify_checksum_and_release_private_key_piece(checksum, t_start, t_end, verify_nonce)
        
        # 4. Decrypt
        k_final = alice_derive_final_key(keys["k_public"], keys["k_private"])
        decrypted = alice_decrypt(ciphertext, k_final, nonce)
        print(f"DEBUG: Decrypted bytes: {decrypted}")
        
        # In v3, the decrypted payload is the Session Key (bytes), not a string.
        # We return it as hex so the client can import it.
        return jsonify({"plaintext": decrypted.hex()})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/reset', methods=['POST'])
def reset():
    global server_instance
    # Close existing connection if any (not needed with context managers)
    
    # Delete the DB file to truly reset
    import os
    if os.path.exists("server_state.db"):
        os.remove("server_state.db")
        
    server_instance = Server()
    return jsonify({"message": "Server reset complete"})

if __name__ == '__main__':
    # Start the Timekeeper in the background
    t = threading.Thread(target=ticker_loop, daemon=True)
    t.start()
    
    app.run(port=5001)
