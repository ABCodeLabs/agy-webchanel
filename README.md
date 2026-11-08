# agy-webchanel (`agywc`)

A Python CLI that establishes an **asynchronous, bidirectional context and message channel** between a **Local Agent (Antigravity / AGY)** and **Gemini Web** using Google Drive as a transport layer.

---

## 🤖 Quick Setup Guide for AI Agents (One-Liner)

If a human user asks you (**an AI coding agent**) to *"install and configure `agy-webchanel` (`agywc`) in this repository"*, execute the following steps directly in the target repository:

### Step 1: Install the `agywc` executable globally
Run the official one-liner installer (it automatically installs the standalone binary from GitHub Releases or sets up an isolated environment in `~/.local/bin/agywc`):

```bash
curl -fsSL https://raw.githubusercontent.com/ABCodeLabs/agy-webchanel/main/install.sh | bash
export PATH="$HOME/.local/bin:$PATH"
agywc --help
```

### Step 2: Initialize `.agywc/` in the target repository
Inside the root of the repository you want to connect:

```bash
agywc init
agywc pack
```
This creates `.agywc/` (`AGENTS.md`, `repo-compressed/repo-context.md`, `chat-local/archived/`, `chat-remote/archived/`) and ensures `.agywc/` is added to `.gitignore`.

### Step 3: Authenticate with Google Drive (once per machine/container)
Check if Google Drive credentials are already active:

```bash
agywc status
```
- If `Autenticação Drive` shows **Autenticado**, proceed straight to **Step 4**.
- If not authenticated yet:
  - Ask the user for the path to their OAuth Desktop Client JSON (`credentials.json`) or Service Account JSON.
  - Run:
    ```bash
    # For OAuth2 Desktop Client (starts local listener on port 8085 and prints auth URL):
    agywc auth -c /path/to/credentials.json

    # Or for Service Account:
    agywc auth --service-account /path/to/service_account.json
    ```

### Step 4: Sync with Google Drive & Read the Protocol
Once authenticated, push the repository corpus and `.agywc/AGENTS.md` to Google Drive:

```bash
agywc push
```
Then read `.agywc/AGENTS.md` to follow the message-passing and archiving discipline (`agywc send "..." --push`, `agywc pull`, `agywc inbox --ack`).

---

## Directory Architecture (`.agywc`)

Both in the local repository (`.agywc/`, gitignored) and in Google Drive (`agy-webchanel/<repo-name>/.agywc/`), the structure follows the exact same contract:

```text
agy-webchanel/                        # Root folder in Google Drive (multi-repository)
└── <repo-name>/
    └── .agywc/                       # Mirrored locally at <repo>/.agywc/
        ├── AGENTS.md                 # Inter-agent protocol & read/discard discipline
        ├── repo-compressed/          # Single Source of Truth (Consolidated repository corpus)
        │   ├── repo-context.md       # Directory tree + full source code in a single file
        │   └── repo-context          # (Optional) Native Google Doc copy for Gemini Web
        ├── chat-local/               # Outbox from Local Agent -> Inbox for Gemini Web
        │   ├── msg-<timestamp>.md    # Active (unread) messages
        │   └── archived/             # Processed/archived messages
        └── chat-remote/              # Outbox from Gemini Web -> Inbox for Local Agent
            ├── msg-<timestamp>.md    # Active (unread) messages
            └── archived/             # Processed/archived messages
```

---

## Manual / Developer Installation

### Quick Install (Standalone Binary / Auto-Venv — Linux & macOS)

```bash
curl -fsSL https://raw.githubusercontent.com/ABCodeLabs/agy-webchanel/main/install.sh | bash
```

### From Source (Development)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

This installs the **`agywc`** (short alias) and **`agy-webchanel`** CLI executables.

---

## CLI Commands

| Command | Description |
| :--- | :--- |
| `agywc auth -c credentials.json` | Authenticate with Google Drive via OAuth2 (or `--service-account`). |
| `agywc init` | Initialize `.agywc/` (`AGENTS.md`, `repo-compressed/`, `chat-local/archived/`, `chat-remote/archived/`) in the current repository. |
| `agywc pack` | Consolidate the local repository into `.agywc/repo-compressed/repo-context.md`. |
| `agywc send "message" [-p]` | Create a new `.agywc/chat-local/msg-<YYYYMMDD-HHMMSS>.md` message (and push to Drive if `-p` is passed). |
| `agywc push` | Update `AGENTS.md`, `repo-compressed/`, and upload active `chat-local/` messages to Google Drive. |
| `agywc pull` | Download active `chat-remote/` messages from Google Drive (automatically exporting native Google Docs to `.md`) and auto-archive replied `chat-local/` messages. |
| `agywc inbox [--ack]` | Display unread messages in `.agywc/chat-remote/` (and optionally archive them immediately with `--ack`). |
| `agywc ack [all \| msg-<ts>.md]` | Mark messages as read by moving them to `archived/` both locally and in Google Drive. |
| `agywc sync` | Run the full cycle (`pack` + `pull` + `push`). |
| `agywc status` | Show local status, message queues, and direct Google Drive links. |
| `agywc credits` | Display project authorship, license information, and third-party open-source credits. |

---

## Standalone Compilation (Nuitka)

To build a standalone single-file binary locally along with `THIRD_PARTY_LICENSES.txt`:

```bash
./scripts/build_standalone.sh
```

Multi-platform release binaries (`Linux x86_64`, `macOS arm64`, `Windows x64`) are automatically compiled and published via GitHub Actions ([`.github/workflows/release.yml`](.github/workflows/release.yml)) whenever a version tag (`v*`) is pushed.

---

## License & Credits

Distributed under the **Apache License 2.0** — see [LICENSE](LICENSE) and [NOTICE](NOTICE) for details.

Developed by **[ABCodeLabs](https://abco.dev)** (`https://github.com/ABCodeLabs/agy-webchanel`).
