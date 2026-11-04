# agy-webchanel (`agywc`)

A Python CLI that establishes an **asynchronous, bidirectional context and message channel** between a **Local Agent (Antigravity / AGY)** and **Gemini Web** using Google Drive as a transport layer.

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

## Installation

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

---

## License & Credits

Distributed under the **Apache License 2.0** — see [LICENSE](LICENSE) and [NOTICE](NOTICE) for details.

Developed by **[ABCodeLabs](https://abco.dev)** (`https://github.com/ABCodeLabs/agy-webchanel`).
