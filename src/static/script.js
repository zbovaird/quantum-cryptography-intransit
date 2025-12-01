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
async function sha256(data) {
    return new Uint8Array(await window.crypto.subtle.digest('SHA-256', data));
}

function pack64(num) {
    const buffer = new ArrayBuffer(8);
    const view = new DataView(buffer);
    view.setBigUint64(0, BigInt(num), false); // Big-endian
    return new Uint8Array(buffer);
}

function concat(...arrays) {
    let totalLength = 0;
    for (const arr of arrays) {
        totalLength += arr.length;
    }
    const result = new Uint8Array(totalLength);
    let offset = 0;
    for (const arr of arrays) {
        result.set(arr, offset);
        offset += arr.length;
    }
    return result;
}

async function hkdf(ikm, length, salt, info) {
    const keyMaterial = await window.crypto.subtle.importKey(
        "raw", ikm, "HKDF", false, ["deriveBits"]
    );
    
    // If salt is empty, it should be hashLen zeros. 
    // But WebCrypto might handle empty salt. 
    // Python's HKDF defaults to zeros if salt is None.
    // Let's ensure salt is Uint8Array.
    if (!salt) salt = new Uint8Array(32); // SHA-256 size

    const bits = await window.crypto.subtle.deriveBits(
        {
            name: "HKDF",
            hash: "SHA-256",
            salt: salt,
            info: info
        },
        keyMaterial,
        length * 8
    );
    return new Uint8Array(bits);
}

async function computePublicHistory(seed, salt, steps) {
    const history = [seed];
    let prevX = new Uint8Array(32); // 32 bytes of zeros
    
    for (let t = 0; t < steps; t++) {
        const currentX = history[history.length - 1];
        const tBytes = pack64(t);
        
        // X_{t+1} = SHA256( X_t || X_{t-1} || salt || t )
        const data = concat(currentX, prevX, salt, tBytes);
        const nextX = await sha256(data);
        
        history.push(nextX);
        prevX = currentX;
    }
    return history;
}

async function derivePublicKeyPiece(history, tStart, tEnd) {
    // K_public = SHA256( X_{t_start} || ... || X_{t_end} )
    const windowData = concat(...history.slice(tStart, tEnd + 1));
    return await sha256(windowData);
}

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
        
        const chainLenDisplay = document.getElementById('chain-len');
        if (chainLenDisplay) chainLenDisplay.innerText = data.public_history_len;

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
let computedChecksum = null;
let computedHistory = null;

async function computeChain() {
    if (!currentEncryption) return;
    document.getElementById('decrypt-output').innerText = "Computing public chain locally...";

    log("Starting public chain computation...", "client");
    log(`Evolving chain from t=0 to t=${currentEncryption.t_end}...`, "client");

    const btn = document.querySelector('button[onclick="verifyAndDecrypt()"]');
    btn.disabled = true;
    btn.style.opacity = "0.5";

    try {
        const pubSeed = hex2buf(currentEncryption.public_seed);
        const pubSalt = hex2buf(currentEncryption.public_salt);
        const tEnd = currentEncryption.t_end;
        const tStart = currentEncryption.t_start;

        // 1. Compute History
        computedHistory = await computePublicHistory(pubSeed, pubSalt, tEnd);
        
        // 2. Compute Checksum (K_public)
        const kPublic = await derivePublicKeyPiece(computedHistory, tStart, tEnd);
        computedChecksum = buf2hex(kPublic);

        document.getElementById('decrypt-output').innerText = "Chain computed. Checksum generated. Ready to verify.";
        log(`Chain computed! Derived Checksum: ${computedChecksum.substring(0, 16)}...`, "client");
        chainComputed = true;
        btn.disabled = false;
        btn.style.opacity = "1";
    } catch (e) {
        console.error(e);
        log(`Chain computation failed: ${e.message}`, "error");
    }
}

async function verifyAndDecrypt() {
    if (!currentEncryption) return;
    if (!chainComputed || !computedChecksum) {
        alert("You must compute the public hash chain first to generate the checksum!");
        return;
    }

    try {
        log(`Sending Checksum to server for verification...`, "client");
        
        // Generate a NEW nonce for verification to prevent replay of this request
        const verifyNonce = Array.from(crypto.getRandomValues(new Uint8Array(8)))
            .map(b => b.toString(16).padStart(2, '0')).join('');

        // Call /verify directly
        const res = await fetch('/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                checksum: computedChecksum,
                t_start: currentEncryption.t_start,
                t_end: currentEncryption.t_end,
                request_nonce: verifyNonce
            })
        });
        
        if (!res.ok) {
            const text = await res.text();
            throw new Error(`Server returned ${res.status}: ${text.substring(0, 100)}`);
        }

        const data = await res.json();
        if (data.error) throw new Error(data.error);

        log(`Server verified checksum!`, "server");
        log(`Server advanced state to t=${currentEncryption.t_end} (BURN EVENT)`, "server");
        
        const kPublicServer = hex2buf(data.k_public);
        const kPrivate = hex2buf(data.k_private);
        
        // Verify k_public matches
        if (data.k_public !== computedChecksum) {
            throw new Error("Server returned mismatched k_public! Potential MITM or logic error.");
        }

        log(`Received k_private. Deriving Final Key...`, "client");

        // 3. Derive K_final
        // K_final = HKDF(K_public || K_private, length=32)
        const kPublic = hex2buf(computedChecksum);
        const ikm = concat(kPublic, kPrivate);
        const salt = new TextEncoder().encode("encryption");
        const info = new TextEncoder().encode("aes_gcm_key");
        
        const kFinalBytes = await hkdf(ikm, 32, salt, info);
        const kFinal = await importKey(kFinalBytes);

        log(`Unwrapping Session Key...`, "client");
        
        // 4. Decrypt Wrapped Key
        const wrappedKeyBytes = hex2buf(currentEncryption.ciphertext);
        const nonceBytes = hex2buf(currentEncryption.nonce);
        
        // The wrapped key is the raw bytes of the session key
        const sessionKeyRawBuffer = await window.crypto.subtle.decrypt(
            { name: "AES-GCM", iv: nonceBytes },
            kFinal,
            wrappedKeyBytes
        );
        
        log(`Importing Session Key...`, "client");
        const sessionKey = await importKey(sessionKeyRawBuffer);

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
