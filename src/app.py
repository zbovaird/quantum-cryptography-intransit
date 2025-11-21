from flask import Flask, request, jsonify
from src.server import Server
import binascii

app = Flask(__name__)

# Initialize server
# In a real app, we'd need persistent storage or a singleton that doesn't reset on reload.
# For this PoC, a global variable is fine as long as we don't use multiple workers.
server_instance = Server()

@app.route('/encrypt', methods=['POST'])
def encrypt():
    data = request.json
    plaintext_hex = data.get('plaintext')
    t_start = data.get('t_start')
    t_end = data.get('t_end')
    
    if not all([plaintext_hex, t_start, t_end]):
        return jsonify({"error": "Missing parameters"}), 400
        
    try:
        plaintext = binascii.unhexlify(plaintext_hex)
        result = server_instance.encrypt_for_alice(plaintext, t_start, t_end)
        
        # Convert bytes to hex for JSON response
        response = {
            "ciphertext": result["ciphertext"].hex(),
            "t_start": result["t_start"],
            "t_end": result["t_end"],
            "public_seed": result["public_seed"].hex(),
            "public_salt": result["public_salt"].hex()
        }
        return jsonify(response)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/verify', methods=['POST'])
def verify():
    data = request.json
    checksum_hex = data.get('checksum')
    t_start = data.get('t_start')
    t_end = data.get('t_end')
    
    if not all([checksum_hex, t_start, t_end]):
        return jsonify({"error": "Missing parameters"}), 400
        
    try:
        checksum = binascii.unhexlify(checksum_hex)
        keys = server_instance.verify_checksum_and_release_private_key_piece(checksum, t_start, t_end)
        
        response = {
            "k_public": keys["k_public"].hex(),
            "k_private": keys["k_private"].hex()
        }
        return jsonify(response)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(port=5000)
