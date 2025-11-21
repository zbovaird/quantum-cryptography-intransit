let currentEncryption = null;
let encryptionHistory = [];

async function pollStatus() {
    try {
        const res = await fetch('/status');
        const data = await res.json();

        document.getElementById('server-t').innerText = data.current_t;
        document.getElementById('chain-len').innerText = data.public_history_len;

        updateVisualizer(data.current_t, data.public_history_len);
    } catch (e) {
        console.error("Status poll failed", e);
    }
}

function updateVisualizer(t, len) {
    const viz = document.getElementById('chain-visualizer');
    viz.innerHTML = '';

    // Show last 50 blocks or so
    const start = Math.max(0, len - 50);

    for (let i = start; i < len; i++) {
        const div = document.createElement('div');
        div.className = 'block';
        if (i <= t) div.classList.add('active');
        viz.appendChild(div);
    }
}

async function encrypt() {
    const plaintext = document.getElementById('plaintext').value;
    const tStart = parseInt(document.getElementById('t-start').value);
    const tEnd = parseInt(document.getElementById('t-end').value);

    // Convert plaintext to hex
    const encoder = new TextEncoder();
    const data = encoder.encode(plaintext);
    const hex = Array.from(data).map(b => b.toString(16).padStart(2, '0')).join('');

    try {
        const res = await fetch('/encrypt', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                plaintext: hex,
                t_start: tStart,
                t_end: tEnd
            })
        });

        const json = await res.json();
        if (json.error) throw new Error(json.error);

        // Add original plaintext for display purposes
        json.originalPlaintext = plaintext;

        currentEncryption = json;
        encryptionHistory.push(json);
        renderHistory();

        document.getElementById('encrypt-output').innerHTML = `<span class="success">Encrypted! Ciphertext: ${json.ciphertext.substring(0, 20)}...</span>`;
        loadFromHistory(encryptionHistory.length - 1);

    } catch (e) {
        document.getElementById('encrypt-output').innerHTML = `<span class="error">Error: ${e.message}</span>`;
    }
}

function renderHistory() {
    const list = document.getElementById('history-list');
    if (encryptionHistory.length === 0) {
        list.innerHTML = '<p style="color: #666; font-style: italic;">No messages encrypted yet.</p>';
        return;
    }

    list.innerHTML = '';
    encryptionHistory.forEach((item, index) => {
        const div = document.createElement('div');
        div.className = 'history-item';
        div.onclick = () => loadFromHistory(index);
        div.innerHTML = `
            <div class="msg">"${item.originalPlaintext}"</div>
            <div class="meta">
                <span>Window: [${item.t_start}, ${item.t_end}]</span>
                <span>Tick: ${item.t_end}</span>
            </div>
        `;
        list.appendChild(div);
    });
}

function loadFromHistory(index) {
    const item = encryptionHistory[index];
    currentEncryption = item;
    document.getElementById('ciphertext-input').value = item.ciphertext;
    document.getElementById('nonce-input').value = item.nonce;
    document.getElementById('decrypt-output').innerHTML = "";

    // Highlight selected
    const items = document.querySelectorAll('.history-item');
    items.forEach(el => el.style.borderColor = '#333');
    if (items[index]) items[index].style.borderColor = '#00ff9d';
}

async function computeChain() {
    if (!currentEncryption) return;
    document.getElementById('decrypt-output').innerText = "Simulating Alice computing chain... (Client-side logic handled by server in this demo)";
    // In a real web app, we'd do WASM or JS crypto.
    // Here we just acknowledge we have the seed.
    setTimeout(() => {
        document.getElementById('decrypt-output').innerText = "Chain computed. Ready to verify.";
    }, 500);
}

async function verifyAndDecrypt() {
    if (!currentEncryption) return;

    // In this web demo, we cheat slightly by asking the server to verify
    // using the checksum we would have computed.
    // Since we don't have JS SHA256 implemented here, we'll rely on the python client logic
    // but we can simulate the request flow.

    // Actually, to make this work without re-implementing crypto in JS,
    // we can use a helper endpoint or just rely on the fact that we are demonstrating the *flow*.
    // Let's try to actually call the verify endpoint.

    // We need the checksum.
    // Since we can't easily compute it in vanilla JS without a library,
    // let's add a helper endpoint to the server to "simulate_alice_work"
    // or just implement a basic SHA256 in JS?
    // Better: Add a /client-helper endpoint to app.py that does the "Alice" work
    // given the seed, just for the sake of the web UI demo.

    try {
        const res = await fetch('/client-helper', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentEncryption)
        });
        const data = await res.json();

        if (data.error) throw new Error(data.error);

        // Now we have keys, let's decrypt (also helper or JS?)
        // Let's use the helper for decryption too to keep JS simple
        document.getElementById('decrypt-output').innerHTML = `<span class="success">Decrypted: ${data.plaintext}</span>`;

    } catch (e) {
        document.getElementById('decrypt-output').innerHTML = `<span class="error">Decryption Failed: ${e.message}</span>`;
    }
}

async function resetServer() {
    if (!confirm("Reset server state? This will destroy all current keys.")) return;
    try {
        await fetch('/reset', { method: 'POST' });
        // Clear inputs
        document.getElementById('plaintext').value = "The eagle flies at midnight";
        document.getElementById('t-start').value = "10";
        document.getElementById('t-end').value = "15";
        document.getElementById('ciphertext-input').value = "";
        document.getElementById('nonce-input').value = "";
        document.getElementById('encrypt-output').innerHTML = "";
        document.getElementById('decrypt-output').innerHTML = "";
        currentEncryption = null;
        encryptionHistory = [];
        renderHistory();
        pollStatus();
    } catch (e) {
        console.error("Reset failed", e);
    }
}

// Poll every second
setInterval(pollStatus, 1000);
pollStatus();
