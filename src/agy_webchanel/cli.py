"""Interface de linha de comando (CLI) do agy-webchanel (agywc)."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agy_webchanel.config import (
    GLOBAL_CONFIG_DIR,
    WorkspacePaths,
    get_global_credentials_path,
    get_global_token_path,
    get_service_account_path,
)
from agy_webchanel.gdrive import (
    GDriveAuthError,
    GDriveClient,
    authenticate_oauth,
    file_url,
    folder_url,
)
from agy_webchanel.mailbox import (
    archive_local_file,
    create_local_message,
    list_messages,
)
from agy_webchanel.packer import pack_repository

app = typer.Typer(
    name="agywc",
    help="Canal bidirecional de contexto e mensagens entre o Agente Local (AGY) e o Gemini Web via Google Drive (.agywc).",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _resolve_paths(repo: Optional[Path]) -> WorkspacePaths:
    root = (repo or Path.cwd()).resolve()
    return WorkspacePaths(root)


@app.command("auth")
def cmd_auth(
    credentials: Optional[Path] = typer.Option(
        None,
        "--credentials",
        "-c",
        help="Caminho para o arquivo credentials.json (OAuth Desktop Client do Google Cloud).",
    ),
    service_account: Optional[Path] = typer.Option(
        None,
        "--service-account",
        "-s",
        help="Caminho para um arquivo JSON de Service Account do Google Cloud.",
    ),
    headless: bool = typer.Option(
        True,
        "--headless/--browser",
        help="Usa modo headless (exibe URL para copiar/colar no container) ou tenta abrir navegador local.",
    ),
) -> None:
    """Configura e autentica o acesso ao Google Drive."""
    if service_account:
        sa_src = service_account.expanduser().resolve()
        if not sa_src.exists():
            console.print(f"[red]Arquivo de Service Account não encontrado:[/red] {sa_src}")
            raise typer.Exit(code=1)
        target = get_service_account_path()
        shutil.copy2(sa_src, target)
        console.print(f"[green]✓ Service Account configurada em:[/green] {target}")
        return

    try:
        token_path = authenticate_oauth(credentials_file=credentials, headless=headless)
        console.print(f"[green]✓ Autenticação OAuth concluída! Token salvo em:[/green] {token_path}")
    except GDriveAuthError as exc:
        console.print(f"[red]Erro de autenticação:[/red] {exc}")
        raise typer.Exit(code=1)


@app.command("init")
def cmd_init(
    repo: Optional[Path] = typer.Option(None, "--repo", "-r", help="Caminho do repositório local."),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Nome do repositório no Google Drive."),
    gdoc: bool = typer.Option(
        True,
        "--gdoc/--no-gdoc",
        help="Criar também uma cópia Google Doc nativa do repo-context para facilitar leitura no Gemini Web.",
    ),
    remote: bool = typer.Option(
        False,
        "--remote",
        help="Já criar imediatamente a estrutura de pastas agy-webchanel/<repo>/.agywc no Google Drive.",
    ),
) -> None:
    """Inicializa a estrutura .agywc/ (AGENTS.md, repo-compressed, chat-local, chat-remote) e configura o .gitignore."""
    paths = _resolve_paths(repo)
    state = paths.ensure_structure(repo_name=name)
    state.create_gdoc = gdoc
    paths.save_state(state)

    console.print(
        Panel.fit(
            f"[bold green]✓ Estrutura local `.agywc/` inicializada![/bold green]\n"
            f"• Repositório: [cyan]{state.repo_name}[/cyan]\n"
            f"• Protocolo dos Agentes: [dim]{paths.agents_md_file}[/dim]\n"
            f"• Corpus Comprimido: [dim]{paths.repo_compressed_dir}[/dim]\n"
            f"• Fila Local -> Remoto: [dim]{paths.chat_local_dir}[/dim]\n"
            f"• Fila Remoto -> Local: [dim]{paths.chat_remote_dir}[/dim]",
            title="agy-webchanel init",
        )
    )

    if remote:
        try:
            client = GDriveClient()
            client.ensure_remote_hierarchy(state)
            paths.save_state(state)
            console.print(
                f"[green]✓ Hierarquia remota criada no Google Drive:[/green] "
                f"agy-webchanel/{state.repo_name}/.agywc\n"
                f"  Link: {folder_url(state.folders.agywc_id)}"
            )
        except GDriveAuthError as exc:
            console.print(f"[yellow]Aviso:[/yellow] Estrutura local criada, mas o Drive não está autenticado ({exc}).")


@app.command("pack")
def cmd_pack(
    repo: Optional[Path] = typer.Option(None, "--repo", "-r", help="Caminho do repositório local."),
) -> None:
    """Comprime/consolida todo o conteúdo do repositório em .agywc/repo-compressed/repo-context.md."""
    paths = _resolve_paths(repo)
    state = paths.ensure_structure()

    result = pack_repository(
        repo_root=paths.repo_root,
        output_path=paths.repo_context_file,
        repo_name=state.repo_name,
        extra_excludes=state.extra_excludes,
    )
    size_kb = result.total_bytes / 1024.0
    console.print(
        f"[green]✓ Repositório consolidado em:[/green] [bold]{result.output_path.relative_to(paths.repo_root)}[/bold]\n"
        f"  Arquivos: [cyan]{result.files_count}[/cyan] | "
        f"Linhas: [cyan]{result.total_lines}[/cyan] | "
        f"Tamanho: [cyan]{size_kb:.1f} KB[/cyan] | "
        f"Commit: [cyan]{result.commit_hash or 'N/A'}[/cyan]"
    )


@app.command("send")
def cmd_send(
    message: Optional[str] = typer.Argument(None, help="Texto da mensagem para enviar ao Gemini Web."),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="Lê o corpo da mensagem a partir de um arquivo Markdown."),
    subject: Optional[str] = typer.Option(None, "--subject", "-s", help="Assunto resumido da mensagem."),
    archive_previous: bool = typer.Option(
        True,
        "--archive-previous/--keep-previous",
        help="Move mensagens anteriores de chat-local/ para chat-local/archived/ antes de criar a nova.",
    ),
    push: bool = typer.Option(False, "--push", "-p", help="Já sincroniza imediatamente com o Google Drive após criar."),
    repo: Optional[Path] = typer.Option(None, "--repo", "-r", help="Caminho do repositório local."),
) -> None:
    """Cria uma mensagem msg-<timestamp>.md em .agywc/chat-local/ para o Gemini Web."""
    paths = _resolve_paths(repo)
    state = paths.ensure_structure()

    if file:
        if not file.exists():
            console.print(f"[red]Arquivo não encontrado:[/red] {file}")
            raise typer.Exit(code=1)
        body = file.read_text(encoding="utf-8")
    elif message:
        body = message
    else:
        console.print("[red]Informe o texto da mensagem ou use `--file <arquivo.md>`.[/red]")
        raise typer.Exit(code=1)

    if archive_previous:
        prev_msgs = list_messages(paths, direction="local", include_archived=False)
        for prev in prev_msgs:
            archive_local_file(paths, direction="local", filename=prev.filename)

    msg = create_local_message(paths=paths, repo_name=state.repo_name, body=body, subject=subject)
    console.print(
        f"[green]✓ Mensagem criada em:[/green] [bold]{msg.path.relative_to(paths.repo_root)}[/bold]"
    )

    if push:
        cmd_push(repo=repo, pack=True)


@app.command("push")
def cmd_push(
    repo: Optional[Path] = typer.Option(None, "--repo", "-r", help="Caminho do repositório local."),
    pack: bool = typer.Option(True, "--pack/--no-pack", help="Atualiza o repo-compressed antes de enviar."),
) -> None:
    """Atualiza o corpus repo-compressed, o AGENTS.md e envia mensagens de chat-local/ para o Google Drive."""
    paths = _resolve_paths(repo)
    state = paths.ensure_structure()

    if pack:
        pack_res = pack_repository(
            repo_root=paths.repo_root,
            output_path=paths.repo_context_file,
            repo_name=state.repo_name,
            extra_excludes=state.extra_excludes,
        )
        state.last_commit_pushed = pack_res.commit_hash

    try:
        client = GDriveClient()
        state, uploaded_msgs = client.push_workspace(paths, state)
        state.last_push_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        paths.save_state(state)
    except GDriveAuthError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    console.print(
        Panel.fit(
            f"[bold green]✓ Push concluído para `agy-webchanel/{state.repo_name}/.agywc`![/bold green]\n"
            f"• Pasta `.agywc` no Drive: {folder_url(state.folders.agywc_id)}\n"
            f"• Corpus (`repo-context.md`): {file_url(state.files.repo_context_md_id)}\n"
            f"• Corpus (Google Doc): {file_url(state.files.repo_context_gdoc_id, is_gdoc=True)}\n"
            f"• Mensagens ativas em `chat-local/`: [cyan]{len(uploaded_msgs)}[/cyan] ({', '.join(uploaded_msgs) or 'nenhuma'})",
            title="agy-webchanel push",
        )
    )


@app.command("pull")
def cmd_pull(
    repo: Optional[Path] = typer.Option(None, "--repo", "-r", help="Caminho do repositório local."),
) -> None:
    """Baixa mensagens enviadas pelo Gemini Web em chat-remote/ e arquiva mensagens de chat-local/ já respondidas."""
    paths = _resolve_paths(repo)
    state = paths.ensure_structure()

    try:
        client = GDriveClient()
        state, downloaded, auto_archived = client.pull_remote_messages(paths, state)
        state.last_pull_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        paths.save_state(state)
    except GDriveAuthError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    if downloaded:
        console.print(f"[bold green]✓ {len(downloaded)} mensagem(ns) ativa(s) em `.agywc/chat-remote/`:[/bold green]")
        for p in downloaded:
            console.print(f"  • [cyan]{p.relative_to(paths.repo_root)}[/cyan]")
    else:
        console.print("[dim]Nenhuma mensagem nova em `chat-remote/`.[/dim]")

    if auto_archived:
        console.print(
            f"[dim]↪ {len(auto_archived)} mensagem(ns) anterior(es) de `chat-local/` movida(s) para `archived/`: "
            f"{', '.join(auto_archived)}[/dim]"
        )


@app.command("inbox")
def cmd_inbox(
    ack: bool = typer.Option(
        False,
        "--ack",
        help="Descarta/arquiva automaticamente as mensagens em chat-remote/archived/ após exibi-las.",
    ),
    repo: Optional[Path] = typer.Option(None, "--repo", "-r", help="Caminho do repositório local."),
) -> None:
    """Exibe o conteúdo das mensagens não lidas em .agywc/chat-remote/."""
    paths = _resolve_paths(repo)
    paths.ensure_structure()
    msgs = list_messages(paths, direction="remote", include_archived=False)

    if not msgs:
        console.print("[dim]Caixa de entrada (`chat-remote/`) vazia.[/dim]")
        return

    for msg in msgs:
        console.print(
            Panel(
                msg.read_content(),
                title=f"[bold cyan]{msg.filename}[/bold cyan] (.agywc/chat-remote/)",
                expand=False,
            )
        )

    if ack:
        cmd_ack(target="all", direction="remote", local_only=False, repo=repo)


@app.command("ack")
def cmd_ack(
    target: str = typer.Argument(
        "all",
        help="Nome do arquivo (ex: msg-20261104-143000.md) ou 'all' para arquivar todas as mensagens ativas.",
    ),
    direction: str = typer.Option(
        "remote",
        "--direction",
        "-d",
        help="Qual fila arquivar: 'remote' (chat-remote) ou 'local' (chat-local).",
    ),
    local_only: bool = typer.Option(
        False,
        "--local-only",
        help="Move apenas localmente sem conectar ao Google Drive.",
    ),
    repo: Optional[Path] = typer.Option(None, "--repo", "-r", help="Caminho do repositório local."),
) -> None:
    """Marca mensagens como lidas, movendo-as da pasta ativa para a subpasta archived/ (local e no Drive)."""
    paths = _resolve_paths(repo)
    state = paths.ensure_structure()

    active_msgs = list_messages(paths, direction=direction, include_archived=False)
    if not active_msgs:
        console.print(f"[dim]Nenhuma mensagem ativa em `chat-{direction}/` para arquivar.[/dim]")
        return

    if target.lower() == "all":
        to_archive = [m.filename for m in active_msgs]
    else:
        fname = target if target.endswith(".md") else f"{target}.md"
        to_archive = [m.filename for m in active_msgs if m.filename == fname]
        if not to_archive:
            console.print(f"[red]Mensagem não encontrada em `chat-{direction}/`:[/red] {fname}")
            raise typer.Exit(code=1)

    client: Optional[GDriveClient] = None
    if not local_only:
        try:
            client = GDriveClient()
        except GDriveAuthError:
            client = None

    for fname in to_archive:
        if client:
            client.archive_message(paths, state, direction=direction, filename=fname)
        else:
            archive_local_file(paths, direction=direction, filename=fname)
        console.print(
            f"[green]✓ Arquivada:[/green] `chat-{direction}/{fname}` -> `chat-{direction}/archived/{fname}`"
        )

    paths.save_state(state)


@app.command("sync")
def cmd_sync(
    repo: Optional[Path] = typer.Option(None, "--repo", "-r", help="Caminho do repositório local."),
) -> None:
    """Executa o ciclo completo: pack (comprime repo) + pull (baixa chat-remote) + push (envia contexto e chat-local)."""
    cmd_pack(repo=repo)
    cmd_pull(repo=repo)
    cmd_push(repo=repo, pack=False)


@app.command("status")
def cmd_status(
    repo: Optional[Path] = typer.Option(None, "--repo", "-r", help="Caminho do repositório local."),
) -> None:
    """Mostra o status atual da estrutura .agywc/, filas de mensagens e links do Google Drive."""
    paths = _resolve_paths(repo)
    state = paths.ensure_structure()

    local_active = list_messages(paths, direction="local", include_archived=False)
    local_arch = list_messages(paths, direction="local", include_archived=True)
    remote_active = list_messages(paths, direction="remote", include_archived=False)
    remote_arch = list_messages(paths, direction="remote", include_archived=True)

    has_token = get_global_token_path().exists() or get_service_account_path().exists()
    has_creds = get_global_credentials_path().exists() or get_service_account_path().exists()

    table = Table(title=f"Status agy-webchanel — {state.repo_name}", show_header=False)
    table.add_column("Chave", style="bold cyan")
    table.add_column("Valor")

    table.add_row("Repositório Local", str(paths.repo_root))
    table.add_row("Pasta .agywc", str(paths.agywc_dir))
    table.add_row("Caminho no Drive", f"agy-webchanel/{state.repo_name}/.agywc")
    table.add_row(
        "Autenticação Drive",
        "[green]Autenticado[/green]"
        if has_token
        else ("[yellow]Credenciais presentes (falta `agywc auth`)[/yellow]" if has_creds else f"[red]Não configurado ({GLOBAL_CONFIG_DIR})[/red]"),
    )
    table.add_row("Link .agywc no Drive", folder_url(state.folders.agywc_id))
    table.add_row(
        "Corpus Comprimido",
        f"{paths.repo_context_file.stat().st_size / 1024:.1f} KB (último commit push: {state.last_commit_pushed or 'N/A'})"
        if paths.repo_context_file.exists()
        else "[yellow]Ainda não gerado (`agywc pack`)[/yellow]",
    )
    table.add_row("Último Push / Pull", f"{state.last_push_at or 'N/A'} / {state.last_pull_at or 'N/A'}")
    table.add_row(
        "Fila chat-local (Outbox)",
        f"[bold]{len(local_active)} ativa(s)[/bold] | {len(local_arch) - len(local_active)} arquivada(s)",
    )
    table.add_row(
        "Fila chat-remote (Inbox)",
        f"[bold green]{len(remote_active)} ativa(s)[/bold green] | {len(remote_arch) - len(remote_active)} arquivada(s)",
    )

    console.print(table)


if __name__ == "__main__":
    app()

