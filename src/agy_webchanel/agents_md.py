"""Generator for the .agywc/AGENTS.md inter-agent protocol manual (Local Agent & Gemini Web)."""

from __future__ import annotations


def render_agents_md(repo_name: str) -> str:
    """Return the English content for .agywc/AGENTS.md for the given repository."""
    return f"""# Inter-Agent Communication Protocol (`agy-webchanel`) — `{repo_name}`

This directory (`.agywc`) is a shared asynchronous communication channel between two interlocutors:
1. **Local Agent (AGY):** Operates in the local development environment with read/write access to the `{repo_name}` Git repository and the `agywc` CLI.
2. **Remote Agent (Gemini Web):** Operates in the Gemini web interface with access to Google Drive at `agy-webchanel/{repo_name}/.agywc`.

---

## 1. Directory Structure

```text
agy-webchanel/{repo_name}/.agywc/
├── AGENTS.md                        # This protocol and message-handling manual
├── repo-compressed/                 # Single Source of Truth for the repository codebase
│   └── repo-context.md              # Consolidated corpus (directory tree + current source files)
├── chat-local/                      # Messages sent by Local Agent -> to Gemini Web
│   ├── msg-<timestamp>.md           # Active (unread by Gemini Web) messages
│   └── archived/                    # Read and processed messages
└── chat-remote/                     # Messages sent by Gemini Web -> to Local Agent
    ├── msg-<timestamp>.md           # Active (unread by Local Agent) messages
    └── archived/                    # Read and locally applied messages
```

---

## 2. Single Source of Truth (`repo-compressed/`)

- The file `repo-compressed/repo-context.md` (and/or its native Google Doc counterpart `repo-context`) contains the latest consolidated snapshot of the `{repo_name}` repository (branch, latest commit, directory tree, and full file contents).
- **Both interlocutors must treat `repo-compressed/repo-context.md` as the factual truth regarding the current state of the codebase.**
- Whenever the Local Agent modifies repository files, it must update the corpus via `agywc pack` / `agywc push` (or `agywc sync`).

---

## 3. Message Naming & Format (`msg-<timestamp>.md`)

- Each message must be created as a **separate file** named using the UTC timestamp format:
  `msg-YYYYMMDD-HHMMSS.md` (e.g., `msg-20261104-143000.md`).
- **Directional queues:**
  - **`chat-local/`**: Used exclusively by the **Local Agent** to post questions, task contexts, execution reports, or prompts for Gemini Web.
  - **`chat-remote/`**: Used exclusively by **Gemini Web** to post responses, architectural decision records (ADRs), action plans, or specifications for the Local Agent.

### Recommended Message Template

```markdown
---
from: local | remote
repo: {repo_name}
timestamp: YYYY-MM-DDTHH:MM:SSZ
subject: Short summary of the topic
---

# Context / Message

<concise message body, analysis, decision, or instructions>
```

---

## 4. Read & Discard (Archiving) Discipline

To keep context windows clean and avoid re-reading old messages:

1. **Only files at the root of `chat-local/` and `chat-remote/` are active (unread) messages.**
2. **Ignore `archived/` during normal operation:** Files inside `chat-local/archived/` and `chat-remote/archived/` have already been processed and are kept strictly for history/auditing.
3. **How to discard after reading:**
   - **Local Agent (AGY):**
     1. Checks pending messages in `.agywc/chat-remote/msg-*.md` (after running `agywc pull` or `agywc sync`).
     2. Reads active messages in chronological `<timestamp>` order.
     3. Once a message from `chat-remote/` is processed/applied, **discards it from the active queue** by running `agywc ack` (which moves the file from `chat-remote/` to `chat-remote/archived/` both locally and in Google Drive).
   - **Remote Agent (Gemini Web):**
     1. Reads only active messages at the root of `chat-local/msg-*.md` (ignoring `chat-local/archived/`).
     2. Replies by creating a new `msg-<timestamp>.md` document inside `chat-remote/`.
     3. If permitted by the interface to move the read file from `chat-local/` to `chat-local/archived/`, it may do so; otherwise, the `agywc` CLI will automatically move older `chat-local/` messages into `chat-local/archived/` as soon as it detects a newer reply in `chat-remote/` or when sending the next message.
"""
