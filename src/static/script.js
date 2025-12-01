let currentEncryption = null;
let encryptionHistory = [];
let serverCurrentT = 0;

// --- Log Function ---
function log(message, type = 'system') {
    const panel = document.getElementById('protocol-log');
    if (!panel) return;
    const div = document.createElement('div');
    div.className = `log-entry ${type}`;
    div.innerText = `[${new Date().toLocaleTimeString()}] ${message}`;
    panel.appendChild(div);
    panel.scrollTop = panel.scrollHeight;
}

// --- Crypto Helpers ---
async function generateKey() {
    return await window.crypto.subtle.generateKey(
        { name: "AES-GCM", length: 256 },
        true,
        ["encrypt", "decrypt"]
    );
}

async function encryptData(key, plaintext) {
    const iv = window.crypto.getRandomValues(new Uint8Array(12));
    const encoded = new TextEncoder().encode(plaintext);
    const ciphertext = await window.crypto.subtle.encrypt(
        { name: "AES-GCM", iv: iv },
        key,
        encoded
    );
    return { ciphertext, iv };
}

async function decryptData(key, ciphertext, iv) {
    const decrypted = await window.crypto.subtle.decrypt(
        { name: "AES-GCM", iv: iv },
        key,
        ciphertext
    );
    return new TextDecoder().decode(decrypted);
}

async function exportKey(key) {
    return await window.crypto.subtle.exportKey("raw", key);
}

async function importKey(rawKey) {
    return await window.crypto.subtle.importKey(
        "raw",
        rawKey,
        "AES-GCM",
        true,
        ["encrypt", "decrypt"]
    );
}

function buf2hex(buffer) {
    return [...new Uint8Array(buffer)]
        .map(x => x.toString(16).padStart(2, '0'))
        .join('');
}

function hex2buf(hex) {
    return new Uint8Array(hex.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
}

function renderViz(t) {
    const viz = document.getElementById('chain-visualizer');
    if (!viz) return;
    viz.innerHTML = '';
    const start = Math.max(0, t - 5);
    const len = start + 15; // Show 15 blocks

    for (let i = start; i < len; i++) {
        const div = document.createElement('div');
        div.className = 'block';
        div.innerText = i;
        if (i <= t) div.classList.add('active');
        viz.appendChild(div);
    }
}

function updateTimeInputs() {
    const autoStart = document.getElementById('auto-sync-start');
    const autoEnd = document.getElementById('auto-sync-end');
    
    if (autoStart && autoStart.checked) {
        document.getElementById('t-start').value = serverCurrentT + 10;
    }
    
    if (autoEnd && autoEnd.checked) {
        const startVal = parseInt(document.getElementById('t-start').value) || serverCurrentT;
        document.getElementById('t-end').value = startVal + 30;
    }
}

async function pollStatus() {
    try {
        const res = await fetch('/status');
        const data = await res.json();
        serverCurrentT = data.current_t;
        const timeDisplay = document.getElementById('server-t');
        if (timeDisplay) timeDisplay.innerText = serverCurrentT;
        renderViz(serverCurrentT);
        updateTimeInputs();
    } catch (e) {
        console.error("Poll failed", e);
    }
}

async function encrypt() {
    const plaintext = document.getElementById('plaintext').value;
    const tStart = parseInt(document.getElementById('t-start').value);
    const tEnd = parseInt(document.getElementById('t-end').value);

    try {
        log(`Generating ephemeral session key...`, 'client');
        // 1. Generate Session Key
        const sessionKey = await generateKey();
        
        // 2. Encrypt Data locally
        log(`Encrypting data locally with session key...`, 'client');
        const { ciphertext: dataCiphertext, iv: dataIv } = await encryptData(sessionKey, plaintext);
        
        // 3. Export Session Key to send to server
        const rawKey = await exportKey(sessionKey);
        const keyHex = buf2hex(rawKey);
        
        // Generate random nonce for the request
        const nonce = Array.from(crypto.getRandomValues(new Uint8Array(8)))
            .map(b => b.toString(16).padStart(2, '0')).join('');

        log(`Sending Session Key to server for time-locking [${tStart}, ${tEnd}]...`, 'client');
        
        // 4. Send Session Key to Server
        const res = await fetch('/encrypt', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                plaintext: keyHex, // We send the KEY as the plaintext to be locked
                t_start: tStart,
                t_end: tEnd,
                request_nonce: nonce
            })
        });

        const json = await res.json();
        if (json.error) throw new Error(json.error);

        log(`Received Time-Locked Key (Ciphertext): ${json.ciphertext.substring(0, 16)}...`, 'server');

        // 5. Store everything
        // We store the DATA ciphertext and IV locally.
        // We store the KEY ciphertext (from server) to unlock later.
        
        const record = {
            ...json, // server response (ciphertext of key, public_seed, etc)
            dataCiphertext: buf2hex(dataCiphertext),
            dataIv: buf2hex(dataIv),
            originalPlaintext: plaintext // Keep for demo/debug
        };

        currentEncryption = record;
        encryptionHistory.push(record);
        renderHistory();

        document.getElementById('encrypt-output').innerHTML = `<span class="success">Data Encrypted & Key Time-Locked!</span>`;
        loadFromHistory(encryptionHistory.length - 1);

    } catch (e) {
        console.error(e);
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
    
    document.getElementById('data-ciphertext-input').value = item.dataCiphertext;
    document.getElementById('wrapped-key-input').value = item.ciphertext;
    document.getElementById('data-iv-input').value = item.dataIv;
    document.getElementById('nonce-input').value = item.request_nonce;
    
    document.getElementById('decrypt-output').innerHTML = "";

    // Reset chain state
    chainComputed = false;
    const btn = document.querySelector('button[onclick="verifyAndDecrypt()"]');
    if (btn) {
        btn.disabled = false; // We'll let them click it but show the alert, or disable it? 
        // Let's disable it to be clearer, or just rely on the alert. 
        // The previous code block adds the alert. Let's just reset the flag.
    }

    // Highlight selected
    const items = document.querySelectorAll('.history-item');
    items.forEach(el => el.style.borderColor = '#333');
    if (items[index]) items[index].style.borderColor = '#00ff9d';
}

let chainComputed = false;

async function computeChain() {
    if (!currentEncryption) return;
    document.getElementById('decrypt-output').innerText = "Simulating Alice computing chain... (Client-side logic handled by server in this demo)";

    log("Starting public chain computation...", "client");
    log(`Evolving chain from t=0 to t=${currentEncryption.t_end}...`, "client");

    const btn = document.querySelector('button[onclick="verifyAndDecrypt()"]');
    btn.disabled = true;
    btn.style.opacity = "0.5";

    setTimeout(() => {
        document.getElementById('decrypt-output').innerText = "Chain computed. Checksum generated. Ready to verify.";
        log(`Chain computed! Derived Checksum(Public Key Piece).`, "client");
        chainComputed = true;
        btn.disabled = false;
        btn.style.opacity = "1";
    }, 1000);
}

async function verifyAndDecrypt() {
    if (!currentEncryption) return;
    if (!chainComputed) {
        alert("You must compute the public hash chain first to generate the checksum!");
        return;
    }

    try {
        log(`Sending Checksum to server for verification...`, "client");
        // The server will decrypt the SESSION KEY, not the data
        const res = await fetch('/client-helper', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentEncryption)
        });
        const data = await res.json();
        console.log("DEBUG: Received data from server:", data);

        if (data.error) throw new Error(data.error);

        log(`Server verified checksum!`, "server");
        log(`Server advanced state to t=${currentEncryption.t_end} (BURN EVENT)`, "server");
        log(`Received Decrypted Session Key.`, "client");

        // data.plaintext is the HEX encoded session key
        const sessionKeyHex = data.plaintext;
        const sessionKeyRaw = hex2buf(sessionKeyHex);
        
        log(`Importing Session Key...`, "client");
        const sessionKey = await importKey(sessionKeyRaw);

        log(`Decrypting Data locally...`, "client");
        const dataCiphertext = hex2buf(currentEncryption.dataCiphertext);
        const dataIv = hex2buf(currentEncryption.dataIv);

        const decryptedText = await decryptData(sessionKey, dataCiphertext, dataIv);

        document.getElementById('decrypt-output').innerHTML = `<span class="success">Decrypted: ${decryptedText}</span>`;
    } catch (e) {
        log(`Decryption failed: ${e.message} `, "error");
        document.getElementById('decrypt-output').innerHTML = `<span class="error">Decryption Failed: ${e.message}</span>`;
    }
}

let waitInterval = null;

function waitAndDecrypt() {
    if (!currentEncryption) {
        alert("No active encryption to decrypt!");
        return;
    }

    if (!chainComputed) {
        // Auto-compute chain if not done
        computeChain();
    }

    const targetT = currentEncryption.t_end;
    const btn = document.querySelector('button[onclick="waitAndDecrypt()"]');

    if (waitInterval) clearInterval(waitInterval);

    btn.disabled = true;
    btn.innerText = "Waiting...";

    log(`Auto-Decrypt: Waiting for t=${targetT}...`, "info");

    waitInterval = setInterval(() => {
        // Force a poll to get the latest time
        pollStatus();
        
        const timeLeft = targetT - serverCurrentT;

        if (timeLeft > 0) {
            document.getElementById('decrypt-output').innerHTML = `<span style="color: orange">Waiting for time lock... ${timeLeft}s remaining</span>`;
            btn.innerText = `Waiting (${timeLeft}s)...`;
        } else if (timeLeft === 0) {
            // It's time!
            clearInterval(waitInterval);
            waitInterval = null;
            btn.innerText = "Attempting Decrypt...";
            verifyAndDecrypt();
            btn.disabled = false;
            btn.innerText = "3. Wait & Decrypt (Auto)";
        } else {
            // Missed it? Or server jumped ahead? Try anyway if it's close, but server rejects late.
            // If we are late, just try.
            clearInterval(waitInterval);
            waitInterval = null;
            verifyAndDecrypt();
            btn.disabled = false;
            btn.innerText = "3. Wait & Decrypt (Auto)";
        }
    }, 250); // Check 4 times a second
}

async function resetServer() {
    if (!confirm("Reset server state? This will destroy all current keys.")) return;
    try {
        await fetch('/reset', { method: 'POST' });
        // Clear inputs
        document.getElementById('plaintext').value = "The eagle flies at midnight";
        document.getElementById('t-start').value = "10";
        document.getElementById('t-end').value = "15";
        
        document.getElementById('data-ciphertext-input').value = "";
        document.getElementById('wrapped-key-input').value = "";
        document.getElementById('data-iv-input').value = "";
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

// Poll every 250ms to catch the 1-second window reliably
setInterval(pollStatus, 250);
pollStatus();
