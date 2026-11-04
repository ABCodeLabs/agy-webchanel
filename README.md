# agy-webchanel (`agywc`)

CLI em Python que estabelece um **canal bidirecional de contexto e mensagens** entre o **Agente Local (AGY)** e o **Gemini Web** usando o Google Drive como camada de transporte assíncrona.

---

## Arquitetura de Diretórios (`.agywc`)

Tanto no repositório local (em `.agywc/`, ignorado pelo Git) quanto no Google Drive (em `agy-webchanel/<nome-do-repo>/.agywc/`), a estrutura segue o mesmo contrato:

```text
agy-webchanel/                        # Pasta raiz no Google Drive (multi-repositório)
└── <nome-do-repo>/
    └── .agywc/                       # Espelhado localmente em <repo>/.agywc/
        ├── AGENTS.md                 # Manual de protocolo e disciplina de leitura/descarte
        ├── repo-compressed/          # Fonte da verdade (Corpus consolidado do repositório)
        │   ├── repo-context.md       # Árvore de diretórios + código-fonte em arquivo único
        │   └── repo-context          # (Opcional) Cópia em Google Doc nativo para o Gemini Web
        ├── chat-local/               # Mensagens do Agente Local -> para o Gemini Web
        │   ├── msg-<timestamp>.md    # Mensagens ativas (não lidas)
        │   └── archived/             # Mensagens já lidas/processadas
        └── chat-remote/              # Mensagens do Gemini Web -> para o Agente Local
            ├── msg-<timestamp>.md    # Mensagens ativas (não lidas)
            └── archived/             # Mensagens já aplicadas pelo Agente Local
```

---

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Isso disponibiliza os executáveis **`agywc`** (atalho) e **`agy-webchanel`**.

---

## Comandos Principais

| Comando | Descrição |
| :--- | :--- |
| `agywc auth -c credentials.json` | Autentica via OAuth2 com o Google Drive (ou `--service-account`). |
| `agywc init` | Inicializa `.agywc/` (`AGENTS.md`, `repo-compressed/`, `chat-local/archived/`, `chat-remote/archived/`) no repositório atual. |
| `agywc pack` | Comprime/consolida o repositório local em `.agywc/repo-compressed/repo-context.md`. |
| `agywc send "mensagem" [-p]` | Cria um arquivo `.agywc/chat-local/msg-<YYYYMMDD-HHMMSS>.md` (e envia ao Drive se usar `-p`). |
| `agywc push` | Atualiza `AGENTS.md`, `repo-compressed/` e envia mensagens ativas de `chat-local/` para o Google Drive. |
| `agywc pull` | Baixa mensagens ativas de `chat-remote/` do Google Drive (convertendo Google Docs para `.md` se necessário) e arquiva mensagens de `chat-local/` já respondidas. |
| `agywc inbox [--ack]` | Exibe no terminal as mensagens pendentes em `.agywc/chat-remote/` (e opcionalmente já as arquiva com `--ack`). |
| `agywc ack [all \| msg-<ts>.md]` | Descarta/arquiva mensagens lidas movendo-as para `archived/` tanto localmente quanto no Google Drive. |
| `agywc sync` | Executa o ciclo completo (`pack` + `pull` + `push`). |
| `agywc status` | Exibe o status local e links diretos das pastas/arquivos no Google Drive. |

---

## Licença e Créditos

Distribuído sob a licença **Apache License 2.0** — veja [LICENSE](LICENSE) e [NOTICE](NOTICE) para mais detalhes.

Desenvolvido por **[ABCodeLabs](https://abco.dev)** (`https://github.com/ABCodeLabs/agy-webchanel`).

