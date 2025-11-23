# Protocol Breakdown: The Mechanics of Time

## 1. The "Markovian" Question
**User Question:** *"How is it not a non-markovian process if the user must solve the entire puzzle...?"*

**The Answer:**
The system is **Markovian** because the **Server** (the entity holding the secrets) is memoryless.

*   **Markov Property:** The future state depends *only* on the current state, not on the history of how we got here.
    *   Formula: $S_{t+1} = Function(S_t)$
*   **Why this matters for Security:** Because the server only needs $S_t$ to move to $S_{t+1}$, it can **safely delete** $S_t$ immediately after the step. It doesn't need to "remember" $S_0$ or $S_{t-1}$. This is what guarantees that the past is gone forever.
*   **The Client's View:** You are correct that the *Client* must replay the whole history ($X_0 \to X_1 \to ... \to X_t$) to verify the server. But this is just **verification**. The *cryptographic reality*—the existence of the key itself—is purely Markovian. The key exists in the "now," completely detached from the "past."

If the process were **Non-Markovian** (depending on history), the server would have to store the entire history (or the root seed) forever to calculate future keys. If it stored the root seed, a hack today would reveal all past keys. By being Markovian, we ensure a hack today reveals *only* today's key.

---

## 2. Visualizing the Process

### The Diagram (Mermaid)
This diagram shows the two parallel chains: the **Public Chain** (which acts as the clock/verification) and the **Private Chain** (which holds the secrets).

```mermaid
graph TD
    subgraph Public Chain (Visible to Everyone)
        X0[X_0: Genesis] -->|Hash| X1[X_1: Tick 1]
        X1 -->|Hash| X2[X_2: Tick 2]
        X2 -->|Hash| X3[X_3: Tick 3]
    end

    subgraph Private Chain (Hidden on Server)
        S0[S_0: Secret State] -->|Hash + X0| S1[S_1: Secret State]
        S1 -->|Hash + X1| S2[S_2: Secret State]
        S2 -->|Hash + X2| S3[S_3: Secret State]
    end

    subgraph Key Generation (At Tick 2)
        X2 -.->|Combine| K_pub[K_public]
        S2 -.->|Combine| K_priv[K_private]
        K_pub --> K_final[Final AES Key]
        K_priv --> K_final
    end

    style S0 fill:#f96,stroke:#333,stroke-width:2px
    style S1 fill:#f96,stroke:#333,stroke-width:2px
    style S2 fill:#f96,stroke:#333,stroke-width:2px
    style S3 fill:#f96,stroke:#333,stroke-width:2px
    
    style X0 fill:#9cf,stroke:#333,stroke-width:2px
    style X1 fill:#9cf,stroke:#333,stroke-width:2px
    style X2 fill:#9cf,stroke:#333,stroke-width:2px
```

### AI Image Prompts (for DALL-E 3 / Midjourney)
Here are prompts to generate a visual storyboard of the process:

**1. The Setup (Initialization)**
> **Prompt:** "A glowing digital server monolith in a dark void, holding a single radiant red sphere of energy (the Secret State) in its core. A blue crystalline chain (Public Chain) begins to grow from the ground next to it. Cyberpunk aesthetic, cinematic lighting, 8k resolution."

**2. The Promise (Encryption)**
> **Prompt:** "A futuristic holographic interface showing a user 'Alice' sealing a document inside a transparent digital vault. The vault has a timer counting down. A ghostly, translucent key floats inside the vault, representing the future key that does not exist yet. Blue and neon purple color palette."

**3. The Burn (Time Advances)**
> **Prompt:** "Close up of the server monolith. It has generated a new, brighter red sphere of energy. The previous red sphere is crumbling into ash and dissolving into digital dust, symbolizing the destruction of the past key. High contrast, dramatic lighting, particles fading away."

**4. The Unlock (Decryption)**
> **Prompt:** "A user 'Bob' standing before the digital vault. The timer has reached zero. The server monolith shoots a beam of red light into the vault, solidifying the ghostly key into a solid golden key. The vault opens, revealing the glowing document inside. Triumphant atmosphere."

**5. The Lockout (Attacker Fails)**
> **Prompt:** "A shadowy hacker figure trying to open an old, rusted digital vault. The vault is dark and inert. The server monolith in the background has moved far away and turned its back. The hacker holds a handful of ash (the destroyed key), looking frustrated. Dark, moody, glitch art style."

---

## 3. Step-by-Step Breakdown (with Toy Numbers)

Let's imagine our hash function `H(x)` is very simple: it just adds numbers and takes the last digit (modulo 10).
*   **Hash Function:** $H(x) = (x + 1) \% 10$ (Simplified for demo)
*   **Server Secret:** $7$

### Step 1: Initialization (Tick 0)
The server starts.
*   **Public Seed ($X_0$):** `5`
*   **Private State ($S_0$):** `3`
*   **Server Memory:** Holds `S_0 = 3`.

### Step 2: Encryption Request (Alice)
Alice wants to encrypt a file for **Tick 2**.
She asks the server: "Give me the Public Key Piece for Tick 2."
The server (or Alice) computes the Public Chain to Tick 2:
*   $X_1 = H(X_0) = (5+1)\%10 = 6$
*   $X_2 = H(X_1) = (6+1)\%10 = 7$
*   **Public Key Piece ($K_{pub}$):** Let's say it's just $X_2 = 7$.

Alice now needs the **Private Key Piece ($K_{priv}$)**. But the server is at Tick 0 ($S_0=3$). It **simulates** the future to tell Alice what the key *will* be, without actually moving there yet.
*   Future $S_1 = H(S_0 + X_0) = (3+5+1)\%10 = 9$
*   Future $S_2 = H(S_1 + X_1) = (9+6+1)\%10 = 6$
*   **Private Key Piece ($K_{priv}$):** $S_2 = 6$.

Alice combines them:
*   **Final Key:** $K_{pub} + K_{priv} = 7 + 6 = 13$.
Alice encrypts her file with Key `13`. **She saves the file.**

### Step 3: The Wait (Tick 0 -> Tick 1)
Time passes. The server ticks forward.
*   Server computes $S_1 = 9$.
*   **CRITICAL MOMENT:** The server **overwrites** $S_0$ with $S_1$.
*   **Server Memory:** Holds `S_1 = 9`. The value `3` is gone from the universe.

### Step 4: Decryption Attempt (Bob at Tick 2)
Bob has the file. He wants to decrypt it.
1.  **Bob's Proof:** Bob computes the public chain $X_0 \to X_1 \to X_2$ (`5 -> 6 -> 7`). He sends $X_2=7$ to the server as proof he did the work.
2.  **Server Verification:** Server checks: "Is the current public chain at Tick 2 equal to 7? Yes."
3.  **The Burn:** The server is currently at Tick 1 ($S_1=9$). To give Bob the key for Tick 2, it must advance.
    *   Server computes $S_2 = H(S_1 + X_1) = (9+6+1)\%10 = 6$.
    *   **CRITICAL MOMENT:** Server **overwrites** $S_1$ with $S_2$.
    *   **Server Memory:** Holds `S_2 = 6`. The value `9` is gone.
4.  **Key Release:** Server gives Bob $K_{priv} = 6$.
5.  **Decryption:** Bob takes his $K_{pub}$ (7) and the server's $K_{priv}$ (6), adds them ($7+6=13$), and decrypts the file. Success!

### Step 5: The "Too Late" Attempt (Attacker at Tick 3)
An attacker steals the encrypted file and tries to decrypt it later, at Tick 3.
1.  Server is at Tick 3 ($S_3$).
2.  Attacker asks for key for Tick 2.
3.  Server checks: "I am at Tick 3. You want Tick 2. To give you Tick 2, I would need $S_2$."
4.  **The Reality:** The server *only* has $S_3$. To get $S_2$, it would need to reverse the hash function (subtract 1). But hash functions are **one-way**. You cannot go back.
5.  **Result:** The key `13` is mathematically unrecoverable. The file is trash.
