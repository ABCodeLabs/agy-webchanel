"""Consolidador nativo de repositório em arquivo único (.agywc/repo-compressed/repo-context.md)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

import pathspec

DEFAULT_IGNORES = [
    ".git/",
    ".agywc/",
    "internal-docs/",
    "__pycache__/",
    "*.py[cod]",
    "*$py.class",
    ".venv/",
    "venv/",
    "ENV/",
    "env/",
    "node_modules/",
    "dist/",
    "build/",
    "*.egg-info/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "uv.lock",
    "Cargo.lock",
    "*.zip",
    "*.tar.gz",
    "*.tgz",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.ico",
    "*.pdf",
    "*.woff",
    "*.woff2",
    "*.ttf",
    "*.eot",
    "*.mp3",
    "*.mp4",
    "*.mov",
    "*.so",
    "*.dylib",
    "*.dll",
    "*.exe",
    ".DS_Store",
]

EXT_TO_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".jsx": "jsx",
    ".json": "json",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "zsh",
    ".html": "html",
    ".css": "css",
    ".sql": "sql",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".xml": "xml",
    ".dockerfile": "dockerfile",
}


@dataclass
class PackResult:
    output_path: Path
    files_count: int
    total_lines: int
    total_bytes: int
    commit_hash: Optional[str]
    branch: Optional[str]
    included_files: List[str]


def _run_git(repo_root: Path, args: list[str]) -> Optional[str]:
    try:
        res = subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return None


def get_git_info(repo_root: Path) -> tuple[Optional[str], Optional[str], Optional[str]]:
    branch = _run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    commit_hash = _run_git(repo_root, ["rev-parse", "--short", "HEAD"])
    commit_msg = _run_git(repo_root, ["log", "-1", "--pretty=%s"])
    return branch, commit_hash, commit_msg


def is_binary_file(filepath: Path, sample_size: int = 8192) -> bool:
    """Detecta se o arquivo é binário inspecionando bytes nulos no início."""
    try:
        with filepath.open("rb") as f:
            chunk = f.read(sample_size)
        if b"\x00" in chunk:
            return True
        return False
    except OSError:
        return True


def build_pathspec(repo_root: Path, extra_excludes: Optional[Iterable[str]] = None) -> pathspec.PathSpec:
    patterns: list[str] = list(DEFAULT_IGNORES)
    gitignore_path = repo_root / ".gitignore"
    if gitignore_path.exists():
        try:
            lines = gitignore_path.read_text(encoding="utf-8", errors="replace").splitlines()
            patterns.extend(lines)
        except OSError:
            pass
    if extra_excludes:
        patterns.extend(extra_excludes)
    return pathspec.PathSpec.from_lines("gitignore", patterns)


def collect_repo_files(
    repo_root: Path,
    extra_excludes: Optional[Iterable[str]] = None,
    max_file_size_bytes: int = 512 * 1024,
) -> List[Path]:
    """Varre o repositório e retorna a lista ordenada de arquivos de texto relevantes."""
    spec = build_pathspec(repo_root, extra_excludes)
    collected: List[Path] = []

    for path in sorted(repo_root.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(repo_root).as_posix()
        if spec.match_file(rel):
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > max_file_size_bytes:
            continue
        if is_binary_file(path):
            continue
        collected.append(path)

    return collected


def render_tree(rel_paths: List[str]) -> str:
    """Gera uma representação em árvore ASCII a partir de caminhos relativos."""
    tree: dict = {}
    for rel in sorted(rel_paths):
        parts = rel.split("/")
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = None

    lines: list[str] = ["."]

    def _walk(subtree: dict, prefix: str = "") -> None:
        items = sorted(subtree.items(), key=lambda kv: (kv[1] is None, kv[0]))
        for idx, (name, child) in enumerate(items):
            is_last = idx == len(items) - 1
            connector = "└── " if is_last else "├── "
            if child is None:
                lines.append(f"{prefix}{connector}{name}")
            else:
                lines.append(f"{prefix}{connector}{name}/")
                extension = "    " if is_last else "│   "
                _walk(child, prefix + extension)

    _walk(tree)
    return "\n".join(lines)


def _guess_lang(path: Path) -> str:
    if path.name.lower() == "dockerfile":
        return "dockerfile"
    return EXT_TO_LANG.get(path.suffix.lower(), "")


def pack_repository(
    repo_root: Path,
    output_path: Path,
    repo_name: Optional[str] = None,
    extra_excludes: Optional[Iterable[str]] = None,
) -> PackResult:
    """Consolida todo o repositório em um único arquivo Markdown estruturado."""
    repo_root = repo_root.resolve()
    name = repo_name or repo_root.name
    files = collect_repo_files(repo_root, extra_excludes=extra_excludes)
    rel_paths = [f.relative_to(repo_root).as_posix() for f in files]

    branch, commit_hash, commit_msg = get_git_info(repo_root)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    sections: list[str] = []
    sections.append(f"# Corpus de Contexto do Repositório: `{name}`\n")
    sections.append(
        "> Este documento é a **Fonte Única da Verdade** sobre o código-fonte do repositório, "
        "gerado automaticamente pelo `agy-webchanel` (`agywc`).\n"
    )
    sections.append("## 1. Metadados do Snapshot\n")
    sections.append(f"- **Repositório:** `{name}`")
    sections.append(f"- **Gerado em (UTC):** `{now_iso}`")
    if branch:
        sections.append(f"- **Branch:** `{branch}`")
    if commit_hash:
        commit_info = f"`{commit_hash}`" + (f" — {commit_msg}" if commit_msg else "")
        sections.append(f"- **Último Commit:** {commit_info}")
    sections.append(f"- **Total de Arquivos Incluídos:** `{len(files)}`\n")

    sections.append("## 2. Árvore de Diretórios\n")
    sections.append("```text")
    sections.append(render_tree(rel_paths))
    sections.append("```\n")

    sections.append("## 3. Conteúdo dos Arquivos\n")

    total_lines = 0
    for file_path, rel in zip(files, rel_paths):
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        file_lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        total_lines += file_lines
        lang = _guess_lang(file_path)

        # Usa 4 crases caso o arquivo possua blocos de 3 crases internamente
        fence = "````" if "```" in content else "```"
        sections.append(f"### File: `{rel}`\n")
        sections.append(f"{fence}{lang}")
        sections.append(content.rstrip("\n"))
        sections.append(f"{fence}\n")

    full_text = "\n".join(sections)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(full_text, encoding="utf-8")
    total_bytes = output_path.stat().st_size

    return PackResult(
        output_path=output_path,
        files_count=len(files),
        total_lines=total_lines,
        total_bytes=total_bytes,
        commit_hash=commit_hash,
        branch=branch,
        included_files=rel_paths,
    )

