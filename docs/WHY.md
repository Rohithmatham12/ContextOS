# ContextOS vs No ContextOS

## The Problem (Without ContextOS)

Imagine you're building an app with **500 files** of code. You need help from an AI (Claude, ChatGPT, etc.).

**What most people do:**
1. Open files manually, copy-paste code into the AI chat
2. Hit the AI's limit — "too much text, try again"
3. Guess which files to include, miss the important ones
4. AI gives wrong answers because it's missing context
5. Repeat until frustrated

```
You → copy random files → AI chat → AI confused → wrong answer
```

---

## The Solution (With ContextOS)

ContextOS reads your whole project automatically and **picks the right files** for you.

```
You → describe your task → ContextOS picks the best files → AI chat → correct answer
```

**One real example:**

| | Without ContextOS | With ContextOS |
|---|---|---|
| Files looked at | 3-5 (guessed manually) | 2,811 (entire repo) |
| Files sent to AI | 3-5 (random) | 12 (the right ones) |
| Secrets exposed | Maybe | Never (auto-removed) |
| Tokens used | Unknown, often over limit | Exactly 7,998 / 8,000 |
| AI answer quality | Hit or miss | Accurate |

---

## What ContextOS Does In 4 Steps

### Step 1 — Scan your project
```
contextos scan
```
Reads all your files. Understands what each one does. Never sends anything to the internet.

### Step 2 — Tell it your task
```
contextos task "add rate limiting to the login page"
```
Plain English. No technical knowledge needed.

### Step 3 — Pack the right files
```
contextos pack --budget 8000
```
Picks only the files relevant to your task. Removes passwords and API keys automatically.

### Step 4 — Open in your AI tool
```
contextos export --format claude
```
Opens Claude (or ChatGPT, Cursor, etc.) with exactly the right context loaded.

---

## Side-by-Side Result

**Without ContextOS** — you paste 3 random files, AI says:
> "I don't see where the authentication happens. Can you share the auth module?"

**With ContextOS** — AI gets the 12 right files and says:
> "In `auth/middleware.py` line 47, add this rate limiter..."

---

## Key Benefits (Plain English)

- **Saves time** — no manual file hunting
- **Better AI answers** — AI has exactly what it needs
- **Safe** — passwords and API keys never leave your machine
- **Works with any AI** — Claude, ChatGPT, Cursor, Aider, Codex

---

## Install (30 seconds)

```bash
pip install rm-contextos
```

That's it. No account. No cloud. No data sent anywhere.
