"""Cliente Google Drive API v3 para sincronizar a estrutura agy-webchanel/<repo>/.agywc."""

from __future__ import annotations

import io
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from agy_webchanel.config import (
    AGYWC_DIR_NAME,
    DRIVE_ROOT_FOLDER_NAME,
    WorkspacePaths,
    WorkspaceState,
    get_global_credentials_path,
    get_global_token_path,
    get_service_account_path,
)
from agy_webchanel.mailbox import (
    archive_local_file,
    list_messages,
    normalize_remote_msg_filename,
)

SCOPES = ["https://www.googleapis.com/auth/drive"]
FOLDER_MIME = "application/vnd.google-apps.folder"
GDOC_MIME = "application/vnd.google-apps.document"


class GDriveAuthError(RuntimeError):
    """Erro de autenticação ou falta de credenciais do Google Drive."""


def authenticate_oauth(
    credentials_file: Optional[Path] = None,
    headless: bool = False,
) -> Path:
    """Realiza o fluxo OAuth2 e salva token.json no diretório global."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    cred_path = get_global_credentials_path()
    token_path = get_global_token_path()

    if credentials_file:
        src = Path(credentials_file).expanduser().resolve()
        if not src.exists():
            raise GDriveAuthError(f"Arquivo de credenciais não encontrado: {src}")
        if src != cred_path:
            cred_path.write_bytes(src.read_bytes())

    if not cred_path.exists():
        raise GDriveAuthError(
            f"Credenciais OAuth não encontradas em {cred_path}.\n"
            "Passe o caminho com: agywc auth --credentials /caminho/para/credentials.json"
        )

    creds = None
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(cred_path), SCOPES)
            if headless:
                flow.redirect_uri = "http://localhost:8085/"
                auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
                print("\nAbra a URL abaixo no seu navegador para autorizar o Google Drive:\n")
                print(f"  {auth_url}\n")
                print(
                    "Após autorizar, se o navegador redirecionar para localhost:8085 e não carregar,\n"
                    "copie a URL completa da barra de endereços (ou apenas o parâmetro `code=`) e cole abaixo:"
                )
                raw = input("URL ou código de autorização: ").strip()
                if raw.startswith("http://") or raw.startswith("https://"):
                    parsed = urlparse(raw)
                    qs = parse_qs(parsed.query)
                    code = (qs.get("code") or [""])[0]
                else:
                    code = raw
                if not code:
                    raise GDriveAuthError("Código de autorização vazio ou inválido.")
                flow.fetch_token(code=code)
                creds = flow.credentials
            else:
                creds = flow.run_local_server(port=8085, open_browser=True)

        token_path.write_text(creds.to_json(), encoding="utf-8")

    return token_path


def get_drive_service():
    """Retorna uma instância autenticada da Google Drive API v3."""
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    token_path = get_global_token_path()
    sa_path = get_service_account_path()

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_path.write_text(creds.to_json(), encoding="utf-8")
    elif sa_path.exists():
        creds = service_account.Credentials.from_service_account_file(
            str(sa_path), scopes=SCOPES
        )

    if not creds or not creds.valid:
        raise GDriveAuthError(
            "Não autenticado no Google Drive. Execute primeiro: `agywc auth`"
        )

    return build("drive", "v3", credentials=creds, cache_discovery=False)


class GDriveClient:
    """Encapsula todas as operações de sincronização do .agywc no Google Drive."""

    def __init__(self, service=None) -> None:
        self.service = service or get_drive_service()

    def _find_item(
        self,
        name: str,
        parent_id: Optional[str] = None,
        mime_type: Optional[str] = None,
    ) -> Optional[dict]:
        escaped = name.replace("'", "\\'")
        q_parts = [f"name = '{escaped}'", "trashed = false"]
        if parent_id:
            q_parts.append(f"'{parent_id}' in parents")
        if mime_type:
            q_parts.append(f"mimeType = '{mime_type}'")
        query = " and ".join(q_parts)
        resp = (
            self.service.files()
            .list(
                q=query,
                spaces="drive",
                fields="files(id, name, mimeType, webViewLink, createdTime, modifiedTime)",
                pageSize=5,
            )
            .execute()
        )
        files = resp.get("files", [])
        return files[0] if files else None

    def _verify_exists(self, file_id: Optional[str]) -> bool:
        if not file_id:
            return False
        try:
            meta = (
                self.service.files()
                .get(fileId=file_id, fields="id, trashed")
                .execute()
            )
            return not meta.get("trashed", False)
        except Exception:
            return False

    def ensure_folder(
        self,
        name: str,
        parent_id: Optional[str] = None,
        cached_id: Optional[str] = None,
    ) -> str:
        """Retorna o ID da pasta no Drive, criando-a se não existir."""
        if cached_id and self._verify_exists(cached_id):
            return cached_id

        found = self._find_item(name=name, parent_id=parent_id, mime_type=FOLDER_MIME)
        if found:
            return found["id"]

        metadata: dict = {"name": name, "mimeType": FOLDER_MIME}
        if parent_id:
            metadata["parents"] = [parent_id]

        created = (
            self.service.files()
            .create(body=metadata, fields="id")
            .execute()
        )
        return created["id"]

    def ensure_remote_hierarchy(self, state: WorkspaceState) -> WorkspaceState:
        """
        Garante a árvore completa no Google Drive:
        agy-webchanel/
          └── <repo_name>/
                └── .agywc/
                      ├── repo-compressed/
                      ├── chat-local/
                      │     └── archived/
                      └── chat-remote/
                            └── archived/
        """
        f = state.folders
        f.root_id = self.ensure_folder(DRIVE_ROOT_FOLDER_NAME, parent_id=None, cached_id=f.root_id)
        f.repo_id = self.ensure_folder(state.repo_name, parent_id=f.root_id, cached_id=f.repo_id)
        f.agywc_id = self.ensure_folder(AGYWC_DIR_NAME, parent_id=f.repo_id, cached_id=f.agywc_id)
        f.repo_compressed_id = self.ensure_folder(
            "repo-compressed", parent_id=f.agywc_id, cached_id=f.repo_compressed_id
        )
        f.chat_local_id = self.ensure_folder(
            "chat-local", parent_id=f.agywc_id, cached_id=f.chat_local_id
        )
        f.chat_local_archived_id = self.ensure_folder(
            "archived", parent_id=f.chat_local_id, cached_id=f.chat_local_archived_id
        )
        f.chat_remote_id = self.ensure_folder(
            "chat-remote", parent_id=f.agywc_id, cached_id=f.chat_remote_id
        )
        f.chat_remote_archived_id = self.ensure_folder(
            "archived", parent_id=f.chat_remote_id, cached_id=f.chat_remote_archived_id
        )
        return state

    def upsert_file(
        self,
        local_path: Path,
        parent_id: str,
        remote_name: Optional[str] = None,
        cached_id: Optional[str] = None,
        target_mime: Optional[str] = None,
        source_mime: str = "text/markdown",
    ) -> str:
        """Cria ou atualiza um arquivo no Google Drive preservando o mesmo fileId."""
        from googleapiclient.http import MediaFileUpload

        name = remote_name or local_path.name
        file_id = cached_id if self._verify_exists(cached_id) else None
        if not file_id:
            found = self._find_item(name=name, parent_id=parent_id, mime_type=target_mime)
            if found:
                file_id = found["id"]

        media = MediaFileUpload(str(local_path), mimetype=source_mime, resumable=False)

        if file_id:
            updated = (
                self.service.files()
                .update(fileId=file_id, media_body=media, fields="id")
                .execute()
            )
            return updated["id"]
        else:
            body: dict = {"name": name, "parents": [parent_id]}
            if target_mime:
                body["mimeType"] = target_mime
            created = (
                self.service.files()
                .create(body=body, media_body=media, fields="id")
                .execute()
            )
            return created["id"]

    def move_file_to_folder(self, file_id: str, old_parent_id: str, new_parent_id: str) -> None:
        """Move um arquivo no Google Drive de uma pasta (ex: ativa) para outra (ex: archived/)."""
        self.service.files().update(
            fileId=file_id,
            addParents=new_parent_id,
            removeParents=old_parent_id,
            fields="id, parents",
        ).execute()

    def list_folder_files(self, folder_id: str) -> List[dict]:
        """Lista todos os arquivos (exceto pastas) dentro de uma pasta do Drive."""
        query = (
            f"'{folder_id}' in parents and "
            f"mimeType != '{FOLDER_MIME}' and "
            f"trashed = false"
        )
        resp = (
            self.service.files()
            .list(
                q=query,
                spaces="drive",
                fields="files(id, name, mimeType, createdTime, modifiedTime, webViewLink)",
                orderBy="createdTime asc",
                pageSize=100,
            )
            .execute()
        )
        return resp.get("files", [])

    def download_file_as_text(self, file_meta: dict) -> str:
        """Baixa o conteúdo de um arquivo .md/.txt ou exporta um Google Doc para Markdown/Texto."""
        from googleapiclient.http import MediaIoBaseDownload

        file_id = file_meta["id"]
        mime = file_meta.get("mimeType", "")
        buf = io.BytesIO()

        if mime == GDOC_MIME:
            # Tenta exportar como Markdown nativo do Drive API v3; fallback para text/plain
            try:
                request = self.service.files().export_media(
                    fileId=file_id, mimeType="text/markdown"
                )
                downloader = MediaIoBaseDownload(buf, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
            except Exception:
                buf = io.BytesIO()
                request = self.service.files().export_media(
                    fileId=file_id, mimeType="text/plain"
                )
                downloader = MediaIoBaseDownload(buf, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
        else:
            request = self.service.files().get_media(fileId=file_id)
            downloader = MediaIoBaseDownload(buf, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

        return buf.getvalue().decode("utf-8", errors="replace")

    def push_workspace(
        self,
        paths: WorkspacePaths,
        state: WorkspaceState,
    ) -> Tuple[WorkspaceState, List[str]]:
        """
        Sincroniza AGENTS.md, repo-compressed/repo-context.md e mensagens ativas de chat-local/ para o Drive.
        Retorna o estado atualizado e a lista de mensagens locais enviadas.
        """
        self.ensure_remote_hierarchy(state)

        # 1. Sincroniza AGENTS.md
        if paths.agents_md_file.exists():
            state.files.agents_md_id = self.upsert_file(
                local_path=paths.agents_md_file,
                parent_id=state.folders.agywc_id,
                remote_name="AGENTS.md",
                cached_id=state.files.agents_md_id,
            )

        # 2. Sincroniza repo-compressed/repo-context.md (e opcionalmente Google Doc nativo)
        if paths.repo_context_file.exists():
            state.files.repo_context_md_id = self.upsert_file(
                local_path=paths.repo_context_file,
                parent_id=state.folders.repo_compressed_id,
                remote_name="repo-context.md",
                cached_id=state.files.repo_context_md_id,
            )
            if state.create_gdoc:
                state.files.repo_context_gdoc_id = self.upsert_file(
                    local_path=paths.repo_context_file,
                    parent_id=state.folders.repo_compressed_id,
                    remote_name="repo-context",
                    cached_id=state.files.repo_context_gdoc_id,
                    target_mime=GDOC_MIME,
                    source_mime="text/markdown",
                )

        # 3. Envia mensagens ativas de chat-local/
        uploaded_msgs: List[str] = []
        active_local = list_messages(paths, direction="local", include_archived=False)
        for msg in active_local:
            existing_id = state.local_msg_ids.get(msg.filename)
            file_id = self.upsert_file(
                local_path=msg.path,
                parent_id=state.folders.chat_local_id,
                remote_name=msg.filename,
                cached_id=existing_id,
            )
            state.local_msg_ids[msg.filename] = file_id
            uploaded_msgs.append(msg.filename)

        return state, uploaded_msgs

    def pull_remote_messages(
        self,
        paths: WorkspacePaths,
        state: WorkspaceState,
        auto_archive_replied_local: bool = True,
    ) -> Tuple[WorkspaceState, List[Path], List[str]]:
        """
        Busca mensagens ativas na pasta chat-remote/ do Google Drive.
        Se encontrar respostas mais recentes que as mensagens ativas em chat-local/,
        arquiva automaticamente as mensagens de chat-local/ já respondidas.
        Retorna (state, lista_de_arquivos_baixados, lista_de_msgs_locais_auto_arquivadas).
        """
        self.ensure_remote_hierarchy(state)
        remote_files = self.list_folder_files(state.folders.chat_remote_id)

        downloaded_paths: List[Path] = []
        latest_remote_ts: Optional[str] = None

        for rf in remote_files:
            norm_name = normalize_remote_msg_filename(
                rf["name"], created_time_iso=rf.get("createdTime")
            )
            # Se já está arquivada localmente, move no Drive também e pula
            if (paths.chat_remote_archived_dir / norm_name).exists():
                try:
                    self.move_file_to_folder(
                        rf["id"],
                        state.folders.chat_remote_id,
                        state.folders.chat_remote_archived_id,
                    )
                except Exception:
                    pass
                continue

            content = self.download_file_as_text(rf)
            local_target = paths.chat_remote_dir / norm_name
            paths.chat_remote_dir.mkdir(parents=True, exist_ok=True)
            local_target.write_text(content, encoding="utf-8")
            state.remote_msg_ids[norm_name] = rf["id"]
            downloaded_paths.append(local_target)

            ts_part = norm_name.removeprefix("msg-").removesuffix(".md")
            if latest_remote_ts is None or ts_part > latest_remote_ts:
                latest_remote_ts = ts_part

        auto_archived_local: List[str] = []
        if auto_archive_replied_local and latest_remote_ts:
            active_local = list_messages(paths, direction="local", include_archived=False)
            for lmsg in active_local:
                if lmsg.timestamp_str <= latest_remote_ts:
                    self.archive_message(paths, state, direction="local", filename=lmsg.filename)
                    auto_archived_local.append(lmsg.filename)

        return state, downloaded_paths, auto_archived_local

    def archive_message(
        self,
        paths: WorkspacePaths,
        state: WorkspaceState,
        direction: str,
        filename: str,
    ) -> bool:
        """
        Move uma mensagem ativa para a subpasta archived/ tanto localmente quanto no Google Drive.
        """
        self.ensure_remote_hierarchy(state)
        archive_local_file(paths, direction=direction, filename=filename)

        if direction == "remote":
            active_folder_id = state.folders.chat_remote_id
            archived_folder_id = state.folders.chat_remote_archived_id
            file_id = state.remote_msg_ids.get(filename)
        elif direction == "local":
            active_folder_id = state.folders.chat_local_id
            archived_folder_id = state.folders.chat_local_archived_id
            file_id = state.local_msg_ids.get(filename)
        else:
            raise ValueError(f"Direção inválida: {direction}")

        if not file_id and active_folder_id:
            found = self._find_item(name=filename, parent_id=active_folder_id)
            if found:
                file_id = found["id"]

        if file_id and active_folder_id and archived_folder_id:
            try:
                self.move_file_to_folder(file_id, active_folder_id, archived_folder_id)
                return True
            except Exception:
                return False
        return False


def folder_url(folder_id: Optional[str]) -> str:
    if not folder_id:
        return "(não sincronizado)"
    return f"https://drive.google.com/drive/folders/{folder_id}"


def file_url(file_id: Optional[str], is_gdoc: bool = False) -> str:
    if not file_id:
        return "(não sincronizado)"
    if is_gdoc:
        return f"https://docs.google.com/document/d/{file_id}/edit"
    return f"https://drive.google.com/file/d/{file_id}/view"

