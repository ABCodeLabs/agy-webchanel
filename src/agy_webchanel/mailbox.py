"""Gerenciamento da fila de mensagens (msg-<timestamp>.md) e arquivamento (archived/)."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from agy_webchanel.config import WorkspacePaths

MSG_FILENAME_RE = re.compile(r"^msg-(\d{8}-\d{6}(?:-\d+)?)\.md$")


@dataclass
class ChatMessage:
    filename: str
    path: Path
    timestamp_str: str
    direction: str  # "local" ou "remote"
    archived: bool = False

    def read_content(self) -> str:
        return self.path.read_text(encoding="utf-8", errors="replace")


def generate_msg_filename(now: Optional[datetime] = None, directory: Optional[Path] = None) -> str:
    """Gera um nome msg-YYYYMMDD-HHMMSS.md único dentro do diretório."""
    dt = now or datetime.now(timezone.utc)
    base_ts = dt.strftime("%Y%m%d-%H%M%S")
    candidate = f"msg-{base_ts}.md"
    if directory is None or not (directory / candidate).exists():
        return candidate
    counter = 1
    while True:
        candidate = f"msg-{base_ts}-{counter:02d}.md"
        if not (directory / candidate).exists():
            return candidate
        counter += 1


def normalize_remote_msg_filename(raw_name: str, created_time_iso: Optional[str] = None) -> str:
    """
    Garante que arquivos criados pelo Gemini Web em chat-remote sigam o padrão msg-<timestamp>.md.
    Se o arquivo já estiver no padrão msg-YYYYMMDD-HHMMSS.md, mantém (adicionando .md se for Google Doc).
    Caso contrário, converte usando o timestamp de criação ou o horário atual.
    """
    clean_name = raw_name.strip()
    if not clean_name.lower().endswith(".md"):
        if clean_name.lower().endswith(".txt"):
            clean_name = clean_name[:-4] + ".md"
        else:
            clean_name = clean_name + ".md"

    if MSG_FILENAME_RE.match(clean_name):
        return clean_name

    # Tenta extrair timestamp de dentro do nome se o usuário/Gemini nomeou parecido
    match = re.search(r"(\d{8}[-_]\d{6})", clean_name)
    if match:
        ts = match.group(1).replace("_", "-")
        return f"msg-{ts}.md"

    if created_time_iso:
        try:
            dt = datetime.fromisoformat(created_time_iso.replace("Z", "+00:00"))
            return f"msg-{dt.strftime('%Y%m%d-%H%M%S')}.md"
        except ValueError:
            pass

    return generate_msg_filename()


def create_local_message(
    paths: WorkspacePaths,
    repo_name: str,
    body: str,
    subject: Optional[str] = None,
) -> ChatMessage:
    """Cria uma nova mensagem do Agente Local em .agywc/chat-local/msg-<timestamp>.md."""
    paths.chat_local_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    filename = generate_msg_filename(now=now, directory=paths.chat_local_dir)
    filepath = paths.chat_local_dir / filename
    ts_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Se o corpo já tiver frontmatter YAML, preserva; caso contrário, adiciona cabeçalho padrão
    if body.lstrip().startswith("---"):
        content = body if body.endswith("\n") else body + "\n"
    else:
        subj_line = f"subject: {subject}\n" if subject else ""
        content = (
            f"---\n"
            f"from: local\n"
            f"repo: {repo_name}\n"
            f"timestamp: {ts_iso}\n"
            f"{subj_line}"
            f"---\n\n"
            f"{body.strip()}\n"
        )

    filepath.write_text(content, encoding="utf-8")
    ts_str = filename.removeprefix("msg-").removesuffix(".md")
    return ChatMessage(
        filename=filename,
        path=filepath,
        timestamp_str=ts_str,
        direction="local",
        archived=False,
    )


def list_messages(
    paths: WorkspacePaths,
    direction: str = "remote",
    include_archived: bool = False,
) -> List[ChatMessage]:
    """Lista mensagens de chat-local ou chat-remote em ordem cronológica."""
    if direction == "local":
        active_dir = paths.chat_local_dir
        archived_dir = paths.chat_local_archived_dir
    elif direction == "remote":
        active_dir = paths.chat_remote_dir
        archived_dir = paths.chat_remote_archived_dir
    else:
        raise ValueError(f"Direção inválida: {direction}")

    messages: List[ChatMessage] = []
    if active_dir.exists():
        for p in sorted(active_dir.glob("msg-*.md")):
            if p.is_file():
                ts = p.name.removeprefix("msg-").removesuffix(".md")
                messages.append(
                    ChatMessage(
                        filename=p.name,
                        path=p,
                        timestamp_str=ts,
                        direction=direction,
                        archived=False,
                    )
                )

    if include_archived and archived_dir.exists():
        for p in sorted(archived_dir.glob("msg-*.md")):
            if p.is_file():
                ts = p.name.removeprefix("msg-").removesuffix(".md")
                messages.append(
                    ChatMessage(
                        filename=p.name,
                        path=p,
                        timestamp_str=ts,
                        direction=direction,
                        archived=True,
                    )
                )

    return messages


def archive_local_file(paths: WorkspacePaths, direction: str, filename: str) -> Optional[Path]:
    """Move um arquivo msg-<timestamp>.md da pasta ativa para a subpasta archived/."""
    if direction == "local":
        src_dir = paths.chat_local_dir
        dst_dir = paths.chat_local_archived_dir
    elif direction == "remote":
        src_dir = paths.chat_remote_dir
        dst_dir = paths.chat_remote_archived_dir
    else:
        raise ValueError(f"Direção inválida: {direction}")

    src = src_dir / filename
    if not src.exists():
        return None
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / filename
    shutil.move(str(src), str(dst))
    return dst

