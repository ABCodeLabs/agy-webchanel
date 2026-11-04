"""Testes automatizados para o pacote agy-webchanel (agywc)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from agy_webchanel.config import WorkspacePaths
from agy_webchanel.mailbox import (
    archive_local_file,
    create_local_message,
    list_messages,
    normalize_remote_msg_filename,
)
from agy_webchanel.packer import pack_repository


def test_ensure_structure_creates_agywc_and_agents_md(tmp_path: Path) -> None:
    paths = WorkspacePaths(tmp_path)
    state = paths.ensure_structure(repo_name="meu-projeto")

    assert state.repo_name == "meu-projeto"
    assert paths.agywc_dir.is_dir()
    assert paths.agents_md_file.is_file()
    assert "meu-projeto" in paths.agents_md_file.read_text(encoding="utf-8")
    assert paths.repo_compressed_dir.is_dir()
    assert paths.chat_local_dir.is_dir()
    assert paths.chat_local_archived_dir.is_dir()
    assert paths.chat_remote_dir.is_dir()
    assert paths.chat_remote_archived_dir.is_dir()
    assert paths.state_file.is_file()
    assert ".agywc/" in (tmp_path / ".gitignore").read_text(encoding="utf-8")


def test_pack_repository_respects_gitignore_and_excludes_agywc(tmp_path: Path) -> None:
    paths = WorkspacePaths(tmp_path)
    paths.ensure_structure(repo_name="demo-repo")

    (tmp_path / ".gitignore").write_text("ignored.txt\n.agywc/\ninternal-docs/\n", encoding="utf-8")
    (tmp_path / "ignored.txt").write_text("segredo", encoding="utf-8")
    (tmp_path / "internal-docs").mkdir()
    (tmp_path / "internal-docs" / "nota.md").write_text("nota interna", encoding="utf-8")

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("def hello():\n    return 'world'\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo Repo\n", encoding="utf-8")

    res = pack_repository(
        repo_root=tmp_path,
        output_path=paths.repo_context_file,
        repo_name="demo-repo",
    )

    assert res.output_path.is_file()
    assert "src/main.py" in res.included_files
    assert "README.md" in res.included_files
    assert "ignored.txt" not in res.included_files
    assert not any(f.startswith(".agywc") for f in res.included_files)
    assert not any(f.startswith("internal-docs") for f in res.included_files)

    packed_text = paths.repo_context_file.read_text(encoding="utf-8")
    assert "def hello():" in packed_text
    assert "segredo" not in packed_text


def test_mailbox_create_list_and_archive(tmp_path: Path) -> None:
    paths = WorkspacePaths(tmp_path)
    paths.ensure_structure(repo_name="demo-repo")

    msg1 = create_local_message(
        paths=paths,
        repo_name="demo-repo",
        body="Preciso revisar a arquitetura de eventos.",
        subject="Revisão de Eventos",
    )
    assert msg1.filename.startswith("msg-")
    assert msg1.filename.endswith(".md")
    assert msg1.path.is_file()

    active = list_messages(paths, direction="local", include_archived=False)
    assert len(active) == 1
    assert active[0].filename == msg1.filename

    archived_path = archive_local_file(paths, direction="local", filename=msg1.filename)
    assert archived_path is not None
    assert archived_path.is_file()
    assert archived_path.parent == paths.chat_local_archived_dir

    active_after = list_messages(paths, direction="local", include_archived=False)
    assert len(active_after) == 0

    all_with_arch = list_messages(paths, direction="local", include_archived=True)
    assert len(all_with_arch) == 1
    assert all_with_arch[0].archived is True


def test_normalize_remote_msg_filename() -> None:
    assert (
        normalize_remote_msg_filename("msg-20261104-143000.md")
        == "msg-20261104-143000.md"
    )
    assert (
        normalize_remote_msg_filename("msg-20261104-143000")
        == "msg-20261104-143000.md"
    )
    assert (
        normalize_remote_msg_filename(
            "Resposta ADR Arquitetura", created_time_iso="2026-11-04T15:20:30Z"
        )
        == "msg-20261104-152030.md"
    )

