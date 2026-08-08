# PraisonAI package map

Source: [MervinPraison/PraisonAI](https://github.com/MervinPraison/PraisonAI)

## Install matrix

| Need | Install |
|------|---------|
| Core Python SDK | `pip install praisonaiagents` |
| Full CLI + integrations | `pip install praisonai` |
| Messaging dashboard | `pip install "praisonai[claw]"` |
| Visual flow builder | `pip install "praisonai[flow]"` |
| Chat UI | `pip install "praisonai[ui]"` |
| JavaScript SDK | `npm install praisonai` |

One-liner installer (upstream):

```bash
curl -fsSL https://praison.ai/install.sh | bash
```

## Monorepo layout (upstream)

```
src/
├── praisonai-agents/     # Core SDK → praisonaiagents
├── praisonai-code/       # Agentic terminal CLI → praisonai_code
├── praisonai-bot/        # Bots / gateway → praisonai_bot
├── praisonai-train/      # Fine-tune + agent training
├── praisonai-browser/    # Browser automation
├── praisonai-mcp/        # MCP server host
├── praisonai-sandbox/    # Sandbox backends
├── praisonai-deploy/     # Deployment
├── praisonai/            # Wrapper: integrations, serve, dashboard
├── praisonai-ts/         # TypeScript SDK
└── praisonai-rust/       # Rust components
```

## Dependency tiers (contributing)

- **Core (`praisonaiagents`)**: protocols, hooks, adapters, Agent/Agents, tools, memory.
- **Tier-2 packages** (`praisonai-code`, `praisonai-bot`, `praisonai-train`, …): must **not** PyPI-depend on the `praisonai` wrapper. Cross-tier access uses lazy `_*_bridge` modules.
- **Wrapper (`praisonai`)**: installs the stack; preserves old `praisonai.*` import paths via shims.

Typical local install order:

`praisonai-agents` → `praisonai-code` → `praisonai-bot` → `praisonai-train` → `praisonai-browser` → `praisonai-mcp` → `praisonai-sandbox` → `praisonai-deploy` → `praisonai`

## Key env vars

| Variable | Used for |
|----------|----------|
| `OPENAI_API_KEY` | Default LLM calls |
| `OPENAI_MODEL_NAME` | Override default model |
| `TAVILY_API_KEY` | Claw built-in web search |
| Provider keys | Anthropic, Gemini, Groq, etc. as configured |

Copy upstream `.env.example` when scaffolding Claw / dashboard setups.

## Docs

- Product docs: https://docs.praison.ai
- Upstream README / examples: https://github.com/MervinPraison/PraisonAI
- MCP registry: `io.github.MervinPraison/praisonai`
