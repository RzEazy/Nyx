# Nyx

```
    ███╗   ██╗██╗   ██╗██╗  ██╗
    ████╗  ██║╚██╗ ██╔╝╚██╗██╔╝
    ██╔██╗ ██║ ╚████╔╝  ╚███╔╝
    ██║╚██╗██║  ╚██╔╝   ██╔██╗
    ██║ ╚████║   ██║   ██╔╝ ██╗
    ╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝
```

**Nyx** is a terminal AI agent with a Textual UI, swappable LLM providers (Cohere by default), SQLite memory, OS tools, and optional RAG.

| | |
|---|---|
| **Author** | Rzy |
| **Owner** | [Cohere](https://cohere.com) (sole ownership) |
| **License** | Proprietary — see [LICENSE](LICENSE) |

---

## Features

- **TUI** — chat, tool traces, typewriter replies, settings modal
- **Providers** — Cohere, OpenAI, Anthropic (via `.env`)
- **Tools** — shell commands, open apps/files, read/write files, system info, file search
- **Sudo** — password prompt in the UI (password stays local, not sent to the model)
- **Memory** — SQLite conversation history + auto-summarization

---

## Requirements

- Python **3.11+** (3.12 recommended)
- Linux, macOS, or Windows (terminal)
- API key for at least one provider (Cohere recommended)

---

## Installation

```bash
git clone https://github.com/YOUR_ORG/Nyx.git
cd Nyx

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env — set COHERE_API_KEY (or another provider)
```

---

## Usage

Start the agent from the project root:

```bash
python -m agent
```

You’ll see an ASCII banner for your OS, then the chat. Examples:

- *“List files in my home directory”*
- *“Open Firefox”*
- *“Run pacman -Q”* (sudo commands open a password dialog)
- *“Write hello to Documents/test.txt”*

### Keybindings

| Key | Action |
|-----|--------|
| `Ctrl+C` | Quit |
| `Ctrl+L` | Clear chat (new session) |
| `Ctrl+S` | Settings — provider & API key |

### Configuration (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_NAME` | `Nyx` | Display name |
| `PROVIDER` | `cohere` | `cohere`, `openai`, or `anthropic` |
| `COHERE_API_KEY` | — | Cohere API key |
| `COHERE_MODEL` | `command-r-plus` | Chat model |
| `OPENAI_API_KEY` | — | OpenAI key |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI model |
| `ANTHROPIC_API_KEY` | — | Anthropic key |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Anthropic model |
| `CHROMA_PATH` | `./data/chroma` | RAG vector store |
| `DB_PATH` | `./data/memory.db` | SQLite memory |
| `MAX_HISTORY` | `20` | Messages before summarize |

Runtime data is stored under `data/` (gitignored).

---

## Development

```bash
source .venv/bin/activate
PYTHONPATH=. pytest tests/ -q
```

---

## Project layout

```
agent/
├── config.py           # Settings & provider factory
├── main.py             # Entry: python -m agent
├── providers/          # Cohere, OpenAI, Anthropic
├── rag/                # ChromaDB retriever
├── memory/             # SQLite history
├── tools/              # OS tools + sudo helpers
├── agent/              # ReAct loop & prompts
└── tui/                # Textual app & styles
tests/
.env.example
```

---

## Security notes

- Never commit `.env` or API keys.
- If an API key was ever committed, **rotate it** in the provider dashboard.
- Sudo passwords are prompted in the TUI only; optionally remembered for the current session until you clear chat.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Random characters when moving the mouse in the input | Fixed in current TUI (mouse capture disabled for input safety). Update to latest. |
| Tools not running | Use `python -m agent` (not legacy scripts). Check API key in `.env` or Ctrl+S. |
| `sudo` commands fail | Enter password in the dialog; ensure `sudo` is installed. |
| Command timeout | Default 10s; very long installs may need to run in a normal terminal. |

---

## Legal

Copyright © Cohere. All rights reserved.  
Created by **Rzy**.  
See [LICENSE](LICENSE) for terms.
