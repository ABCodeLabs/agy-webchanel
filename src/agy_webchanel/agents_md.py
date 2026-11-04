"""Gerador do manual de protocolo .agywc/AGENTS.md para os interlocutores (Agente Local e Gemini Web)."""

from __future__ import annotations


def render_agents_md(repo_name: str) -> str:
    """Retorna o conteúdo do arquivo .agywc/AGENTS.md para o repositório."""
    return f"""# Protocolo de Comunicação Inter-Agentes (`agy-webchanel`) — `{repo_name}`

Este diretório (`.agywc`) é um canal de comunicação assíncrono compartilhado entre dois interlocutores:
1. **Agente Local (AGY):** Opera no ambiente local de desenvolvimento com acesso de leitura/escrita ao repositório Git `{repo_name}` e ao CLI `agywc`.
2. **Agente Remoto (Gemini Web):** Opera na interface web do Gemini com acesso ao Google Drive na pasta `agy-webchanel/{repo_name}/.agywc`.

---

## 1. Estrutura de Diretórios

```text
agy-webchanel/{repo_name}/.agywc/
├── AGENTS.md                        # Este manual de protocolo e disciplina
├── repo-compressed/                 # Fonte da verdade sobre o código do repositório
│   └── repo-context.md              # Corpus consolidado (árvore + código-fonte atual)
├── chat-local/                      # Mensagens enviadas pelo Agente Local -> para o Gemini Web
│   ├── msg-<timestamp>.md           # Mensagens ativas (não lidas pelo Gemini Web)
│   └── archived/                    # Mensagens já lidas e processadas
└── chat-remote/                     # Mensagens enviadas pelo Gemini Web -> para o Agente Local
    ├── msg-<timestamp>.md           # Mensagens ativas (não lidas pelo Agente Local)
    └── archived/                    # Mensagens já lidas e aplicadas localmente
```

---

## 2. Fonte Única da Verdade (`repo-compressed/`)

- O arquivo `repo-compressed/repo-context.md` (e/ou sua versão Google Doc) contém o estado consolidado mais recente do repositório `{repo_name}` (branch, último commit, árvore de arquivos e conteúdo completo).
- **Ambos os interlocutores devem considerar `repo-compressed/repo-context.md` como a verdade factual sobre o código.**
- Sempre que o Agente Local modificar arquivos do repositório, deve atualizar o corpus via `agywc pack` / `agywc push` (ou `agywc sync`).

---

## 3. Convenção de Mensagens (`msg-<timestamp>.md`)

- Cada mensagem deve ser criada como um **arquivo individual** nomeado no formato:
  `msg-YYYYMMDD-HHMMSS.md` (exemplo: `msg-20261104-143000.md`).
- **Direção das pastas:**
  - **`chat-local/`**: Exclusiva para o **Agente Local** publicar perguntas, contextos de tarefa, relatórios de execução ou dúvidas para o Gemini Web.
  - **`chat-remote/`**: Exclusiva para o **Gemini Web** publicar respostas, decisões arquiteturais (ADRs), planos de ação ou especificações para o Agente Local.

### Formato Recomendado da Mensagem

```markdown
---
from: local | remote
repo: {repo_name}
timestamp: YYYY-MM-DDTHH:MM:SSZ
subject: Resumo curto do assunto
---

# Contexto / Mensagem

<conteúdo objetivo da mensagem, análise, decisão ou instrução>
```

---

## 4. Disciplina de Leitura e Descarte (Arquivamento)

Para manter a janela de contexto enxuta e evitar reler mensagens antigas:

1. **Apenas arquivos na raiz de `chat-local/` e `chat-remote/` são mensagens ativas (não lidas).**
2. **Ignorar `archived/` na rotina normal:** Os arquivos dentro de `chat-local/archived/` e `chat-remote/archived/` já foram processados e servem apenas como histórico/auditoria.
3. **Como descartar após a leitura:**
   - **Agente Local (AGY):**
     1. Verifica mensagens pendentes em `.agywc/chat-remote/msg-*.md` (após rodar `agywc pull` ou `agywc sync`).
     2. Lê as mensagens ativas em ordem cronológica de `<timestamp>`.
     3. Após processar/executar o que foi acordado na mensagem, **descarta a mensagem da fila ativa** executando `agywc ack` (que move o arquivo de `chat-remote/` para `chat-remote/archived/` tanto localmente quanto no Google Drive).
   - **Agente Remoto (Gemini Web):**
     1. Lê apenas as mensagens ativas na raiz de `chat-local/msg-*.md` (ignorando `chat-local/archived/`).
     2. Responde criando um novo documento `msg-<timestamp>.md` dentro de `chat-remote/`.
     3. Se tiver permissão na interface para mover o arquivo lido de `chat-local/` para `chat-local/archived/`, pode movê-lo; caso contrário, o CLI `agywc` arquivará automaticamente as mensagens anteriores de `chat-local/` em `chat-local/archived/` assim que detectar a resposta em `chat-remote/` ou no próximo envio.
"""

