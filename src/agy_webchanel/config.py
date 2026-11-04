"""Gerenciamento de diretórios .agywc/, estado local (state.json) e credenciais globais."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Optional

from agy_webchanel.agents_md import render_agents_md

GLOBAL_CONFIG_DIR = Path(
    os.environ.get("AGYWC_CONFIG_DIR", "~/.config/agy-webchanel")
).expanduser()

DRIVE_ROOT_FOLDER_NAME = "agy-webchanel"
AGYWC_DIR_NAME = ".agywc"


@dataclass
class DriveFolderIds:
    """IDs das pastas remotas no Google Drive para evitar buscas repetidas."""

    root_id: Optional[str] = None          # agy-webchanel/
    repo_id: Optional[str] = None          # agy-webchanel/<repo>/
    agywc_id: Optional[str] = None         # agy-webchanel/<repo>/.agywc/
    repo_compressed_id: Optional[str] = None
    chat_local_id: Optional[str] = None
    chat_local_archived_id: Optional[str] = None
    chat_remote_id: Optional[str] = None
    chat_remote_archived_id: Optional[str] = None


@dataclass
class DriveFileIds:
    """IDs de arquivos fixos sincronizados no Google Drive."""

    agents_md_id: Optional[str] = None
    repo_context_md_id: Optional[str] = None
    repo_context_gdoc_id: Optional[str] = None


@dataclass
class WorkspaceState:
    """Estado persistido em .agywc/state.json."""

    repo_name: str
    create_gdoc: bool = True
    last_push_at: Optional[str] = None
    last_pull_at: Optional[str] = None
    last_commit_pushed: Optional[str] = None
    folders: DriveFolderIds = field(default_factory=DriveFolderIds)
    files: DriveFileIds = field(default_factory=DriveFileIds)
    extra_excludes: list[str] = field(default_factory=list)
    remote_msg_ids: Dict[str, str] = field(default_factory=dict)  # filename -> drive_file_id
    local_msg_ids: Dict[str, str] = field(default_factory=dict)   # filename -> drive_file_id

    @classmethod
    def from_dict(cls, data: dict) -> "WorkspaceState":
        folders_data = data.get("folders") or {}
        files_data = data.get("files") or {}
        return cls(
            repo_name=data["repo_name"],
            create_gdoc=data.get("create_gdoc", True),
            last_push_at=data.get("last_push_at"),
            last_pull_at=data.get("last_pull_at"),
            last_commit_pushed=data.get("last_commit_pushed"),
            folders=DriveFolderIds(**folders_data),
            files=DriveFileIds(**files_data),
            extra_excludes=list(data.get("extra_excludes") or []),
            remote_msg_ids=dict(data.get("remote_msg_ids") or {}),
            local_msg_ids=dict(data.get("local_msg_ids") or {}),
        )

    def to_dict(self) -> dict:
        return asdict(self)


class WorkspacePaths:
    """Caminhos padronizados dentro de um repositório local."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.agywc_dir = self.repo_root / AGYWC_DIR_NAME
        self.state_file = self.agywc_dir / "state.json"
        self.agents_md_file = self.agywc_dir / "AGENTS.md"
        self.repo_compressed_dir = self.agywc_dir / "repo-compressed"
        self.repo_context_file = self.repo_compressed_dir / "repo-context.md"
        self.chat_local_dir = self.agywc_dir / "chat-local"
        self.chat_local_archived_dir = self.chat_local_dir / "archived"
        self.chat_remote_dir = self.agywc_dir / "chat-remote"
        self.chat_remote_archived_dir = self.chat_remote_dir / "archived"

    def ensure_structure(self, repo_name: Optional[str] = None) -> WorkspaceState:
        """Garante que toda a árvore .agywc/ exista localmente, incluindo AGENTS.md e state.json."""
        self.repo_compressed_dir.mkdir(parents=True, exist_ok=True)
        self.chat_local_archived_dir.mkdir(parents=True, exist_ok=True)
        self.chat_remote_archived_dir.mkdir(parents=True, exist_ok=True)

        state = self.load_state(default_repo_name=repo_name)
        if repo_name and state.repo_name != repo_name:
            state.repo_name = repo_name

        # Cria ou atualiza AGENTS.md se não existir
        if not self.agents_md_file.exists():
            self.agents_md_file.write_text(
                render_agents_md(state.repo_name), encoding="utf-8"
            )

        self.save_state(state)
        self.ensure_gitignored()
        return state

    def ensure_gitignored(self) -> bool:
        """Garante que .agywc/ esteja listado no .gitignore do repositório."""
        gitignore_path = self.repo_root / ".gitignore"
        entry = ".agywc/"
        if gitignore_path.exists():
            content = gitignore_path.read_text(encoding="utf-8")
            lines = [line.strip() for line in content.splitlines()]
            if entry in lines or ".agywc" in lines:
                return False
            if not content.endswith("\n"):
                content += "\n"
            content += f"\n# Canal de comunicação agy-webchanel\n{entry}\n"
            gitignore_path.write_text(content, encoding="utf-8")
            return True
        else:
            gitignore_path.write_text(
                f"# Canal de comunicação agy-webchanel\n{entry}\n", encoding="utf-8"
            )
            return True

    def load_state(self, default_repo_name: Optional[str] = None) -> WorkspaceState:
        """Carrega o estado de .agywc/state.json ou cria um novo."""
        if self.state_file.exists():
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            return WorkspaceState.from_dict(data)
        name = default_repo_name or self.repo_root.name
        return WorkspaceState(repo_name=name)

    def save_state(self, state: WorkspaceState) -> None:
        """Salva o estado em .agywc/state.json."""
        self.agywc_dir.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(
            json.dumps(state.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def get_global_credentials_path() -> Path:
    GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return GLOBAL_CONFIG_DIR / "credentials.json"


def get_global_token_path() -> Path:
    GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return GLOBAL_CONFIG_DIR / "token.json"


def get_service_account_path() -> Path:
    GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return GLOBAL_CONFIG_DIR / "service_account.json"

