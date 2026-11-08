# AI Agent Instructions for `agy-webchanel` (`agywc`)

If a user asks you to **install, configure, or use `agy-webchanel` (`agywc`)** in any repository, follow this runbook.

---

## 1. Install `agywc` (One-Liner)

Run the official installer script:

```bash
curl -fsSL https://raw.githubusercontent.com/ABCodeLabs/agy-webchanel/main/install.sh | bash
export PATH="$HOME/.local/bin:$PATH"
agywc --help
```

- The installer first attempts to download the precompiled standalone binary (`agywc-linux-x86_64` / `agywc-macos-arm64`) from the latest GitHub Release.
- If a prebuilt binary is not yet available for the current OS/architecture, it automatically creates an isolated Python virtual environment in `~/.local/share/agy-webchanel/venv` (installing `python3` / `python3-venv` if needed) and symlinks `agywc` and `agy-webchanel` into `~/.local/bin`.

---

## 2. Initialize Target Repository

In the root directory of the user's repository:

```bash
agywc init
agywc pack
```

This creates:
- `.agywc/AGENTS.md` (inter-agent communication protocol and message archiving rules)
- `.agywc/repo-compressed/repo-context.md` (consolidated repository snapshot)
- `.agywc/chat-local/archived/` (local-to-remote message queue)
- `.agywc/chat-remote/archived/` (remote-to-local message queue)
- And automatically adds `.agywc/` to `.gitignore`.

---

## 3. Authenticate with Google Drive (If Not Already Authenticated)

Check authentication status:

```bash
agywc status
```

If not authenticated:
1. Ask the user for their Google OAuth Desktop Client JSON (`credentials.json`) or Service Account JSON.
2. Run:
   ```bash
   agywc auth -c /path/to/credentials.json
   ```
   *(In containers/remote environments, `agywc auth` starts a local callback listener on port `8085` and prints the authorization URL for the user to open in their browser).*

---

## 4. Synchronize & Operate

- **Push repository context and outgoing messages to Google Drive:**
  ```bash
  agywc push
  ```
- **Send a message to Gemini Web:**
  ```bash
  agywc send "Your message body here" --subject "Topic" --push
  ```
- **Pull and read replies from Gemini Web (and archive them after processing):**
  ```bash
  agywc pull
  agywc inbox --ack
  ```

Always read `.agywc/AGENTS.md` inside the initialized repository for the full message-passing protocol.
