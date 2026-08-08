---
name: praisonai
description: Build and run PraisonAI agents, multi-agent teams, MCP tools, YAML workflows, and Agent Skills. Use when the user mentions PraisonAI, praisonaiagents, Agent/Agents APIs, praisonai CLI, Claw dashboard, or creating autonomous AI agent workflows in Python, YAML, or JavaScript.
license: MIT
metadata:
  author: creer
  source: https://github.com/MervinPraison/PraisonAI
  docs: https://docs.praison.ai
  version: "1.0"
---

# PraisonAI

Teach the agent how to build with [PraisonAI](https://github.com/MervinPraison/PraisonAI) — a lightweight, agent-centric framework for single agents, multi-agent teams, MCP tools, and production workflows.

## When to Use

- Creating or debugging PraisonAI `Agent` / `Agents` code
- Wiring tools, MCP servers, memory, planning, or handoffs
- Authoring `agents.yaml` or running `praisonai` CLI commands
- Packaging reusable Agent Skills (`SKILL.md`) for PraisonAI
- Choosing between `praisonaiagents` (core SDK) and `praisonai` (full CLI/UI)

## Design principles (always follow)

1. **Minimal API** — prefer existing params (`instructions`, `tools`, `memory`, `hooks`, `skills`) over new abstractions.
2. **Start simple** — one `Agent` + `instructions` first; add multi-agent / MCP / YAML only when needed.
3. **Three surfaces** — every capability should work via **Python**, **YAML**, and **CLI** when documenting or scaffolding.
4. **Safe tools** — never `eval`/`exec` on model or user input; validate tool arguments.

Load more detail only when needed:
- Package map and install matrix → [references/packages.md](references/packages.md)
- API recipes (tools, MCP, YAML, skills) → [references/api-patterns.md](references/api-patterns.md)

## Quick start

```bash
pip install praisonaiagents
export OPENAI_API_KEY="your-api-key"
```

```python
from praisonaiagents import Agent

agent = Agent(instructions="You are a senior data analyst.")
agent.start("Analyze the top 3 tech trends and format as a markdown table.")
```

Full CLI / dashboard / flow extras:

```bash
pip install praisonai                 # wrapper + CLI
pip install "praisonai[claw]"         # messaging dashboard
pip install "praisonai[flow]"         # visual flow builder
pip install "praisonai[ui]"           # chat UI
npm install praisonai                 # JavaScript SDK
```

Default model: `OPENAI_MODEL_NAME` or `gpt-4o-mini`. Set `OPENAI_API_KEY` (and provider-specific keys as needed).

## Core Python patterns

### Single agent

Prefer `instructions=` for simple agents. Use `role` / `goal` / `backstory` when richer persona helps.

```python
from praisonaiagents import Agent

agent = Agent(
    name="Researcher",
    instructions="Research accurately and cite sources.",
    planning=True,       # plan → execute
    memory=True,         # zero-dep memory
    web=True,            # web search/fetch (needs provider keys as required)
)
agent.start("Summarize today's AI news")
# or: agent.chat("Hello") for conversational turns
```

### Multi-agent team

```python
from praisonaiagents import Agent, Agents

researcher = Agent(instructions="Research about AI")
writer = Agent(instructions="Summarise research agent's findings")
team = Agents(agents=[researcher, writer])
team.start()
```

### Custom tools

```python
from praisonaiagents import Agent, tool

@tool
def search(query: str) -> str:
    """Search the web for information."""
    return f"Results for: {query}"

agent = Agent(instructions="You are helpful.", tools=[search])
agent.start("Search for PraisonAI docs")
```

### MCP tools

```python
from praisonaiagents import Agent, MCP

agent = Agent(tools=MCP("npx @modelcontextprotocol/server-memory"))
# HTTP:  MCP("https://api.example.com/mcp")
# WS:    MCP("wss://api.example.com/mcp", auth_token="token")
```

### Agent Skills (SKILL.md)

```python
from praisonaiagents import Agent

agent = Agent(
    name="PDF Assistant",
    instructions="Process PDF documents.",
    skills=["./pdf-processing"],  # dirs containing SKILL.md
)
```

Create skills with CLI:

```bash
praisonai skills create --name my-skill --description "..." --template --output-dir ./skills
```

## Feature flags (agent-centric API)

Most features accept `False` | `True` (defaults) | `Config` object:

| Param | Purpose |
|-------|---------|
| `memory` | Persistent / session memory |
| `knowledge` | RAG sources (paths, URLs, config) |
| `planning` | Plan-then-execute |
| `reflection` | Self-review answer quality |
| `guardrails` | Input/output validation |
| `web` | Web search + fetch |
| `handoffs` | Delegate to other agents |
| `skills` | Load Agent Skills directories |
| `hooks` | Lifecycle hooks |
| `execution` | Code execution / runtime limits |
| `sandbox` | Isolated code execution |
| `llm` / `model` | Model string, dict, or LLMConfig |

Prefer these over inventing new wrapper APIs.

## YAML workflow (no Python)

`agents.yaml`:

```yaml
framework: praisonai
topic: "Write a blog post about AI"

agents:
  researcher:
    role: Research Analyst
    goal: Research AI trends
    instructions: "Find accurate information about AI trends"
  writer:
    role: Content Writer
    goal: Write engaging blog posts
    instructions: "Write clear content based on research"
```

```bash
praisonai agents.yaml
```

## CLI cheat sheet

| Command | Use |
|---------|-----|
| `praisonai agents.yaml` | Run YAML multi-agent job |
| `praisonai skills create ...` | Scaffold a SKILL.md package |
| `praisonai claw` | Claw dashboard (Telegram/Discord/Slack) |
| `praisonai flow` | Langflow visual builder |
| `praisonai ui` | Lightweight chat UI |

## Implementation checklist

When writing or reviewing PraisonAI code:

1. Import from `praisonaiagents` for SDK work; use `praisonai` only for CLI/UI/integrations.
2. Keep agents small — one clear job per agent; compose with `Agents` or `handoffs`.
3. Give every `@tool` a clear docstring (the model uses it as the tool description).
4. Put secrets in env vars (`.env`), never in source or skill files.
5. For monorepo/framework contributions, respect package tiers in [references/packages.md](references/packages.md) — Tier-2 packages must not PyPI-depend on the `praisonai` wrapper.
6. Match existing examples under the upstream `examples/` tree before inventing new patterns.
7. Docs: https://docs.praison.ai — prefer linking users there for deep feature guides.

## Common pitfalls

- **Wrong package**: `praisonaiagents` = core SDK; `praisonai` = full stack. Lightweight scripts should use the core.
- **Missing API key**: set `OPENAI_API_KEY` (or provider key) before `agent.start()`.
- **Over-parameterizing**: don't add custom modules that duplicate `instructions` / `tools` / `memory` / `hooks`.
- **Unsafe tools**: no `eval`/`subprocess` on untrusted input.
- **Deprecated knobs**: prefer `handoffs=` over `allow_delegation=`; prefer `execution=ExecutionConfig(...)` over `allow_code_execution=`.
