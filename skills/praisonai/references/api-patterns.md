# PraisonAI API patterns

Concrete recipes for common tasks. Prefer these over inventing new wrappers.

## Agent constructor essentials

```python
from praisonaiagents import Agent

agent = Agent(
    name="Assistant",
    instructions="Direct system-style instructions (preferred for simple agents).",
    # Or richer persona:
    # role="Data Analyst", goal="...", backstory="...",
    llm="gpt-4o-mini",          # or model= ; also LLMConfig / provider strings
    tools=[...],                # callables, @tool, MCP instances
    handoffs=[other_agent],     # agent-to-agent delegation
    memory=True,
    knowledge=["./docs", "https://example.com"],
    planning=True,
    reflection=True,
    guardrails=True,
    web=True,
    skills=["./skills/pdf-processing"],
    hooks=[...],
)
```

Feature params generally accept:

- `False` — off
- `True` — framework defaults
- Config object / dict / str preset — customized

## Multi-agent

```python
from praisonaiagents import Agent, Agents

a = Agent(instructions="Research")
b = Agent(instructions="Write from research")
Agents(agents=[a, b]).start()
```

Handoffs (explicit delegation):

```python
specialist = Agent(name="Specialist", instructions="Deep dive on finance")
router = Agent(
    name="Router",
    instructions="Route hard finance questions.",
    handoffs=[specialist],
)
```

## Tools

```python
from praisonaiagents import Agent, tool

@tool
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b

Agent(instructions="Math helper", tools=[add]).start("What is 2+3?")
```

Rules:

- Docstring = tool description for the model
- Validate and sanitize inputs
- Never `eval` / `exec` / unchecked `subprocess` on model output

## MCP transports

```python
from praisonaiagents import Agent, MCP

# stdio (local npx/python servers)
Agent(tools=MCP("npx @modelcontextprotocol/server-memory"))

# Streamable HTTP
Agent(tools=MCP("https://api.example.com/mcp"))

# WebSocket
Agent(tools=MCP("wss://api.example.com/mcp", auth_token="token"))

# Explicit command + env
Agent(tools=MCP(
    command="npx",
    args=["-y", "@modelcontextprotocol/server-brave-search"],
    env={"BRAVE_API_KEY": "your-key"},
))
```

## Persistence

```python
from praisonaiagents import Agent, db

agent = Agent(
    name="Assistant",
    db=db(database_url="postgresql://localhost/mydb"),
    session_id="my-session",
)
agent.chat("Hello!")
```

Supports PostgreSQL, MySQL, SQLite, MongoDB, Redis, and more — see docs.

## YAML + custom tool file

`agents.yaml`:

```yaml
framework: praisonai
topic: "Calculate the sum of 25 and 15"
agents:
  calculator_agent:
    role: Calculator
    goal: Perform calculations
    instructions: "Use the add tool"
    tools:
      - add
```

Companion Python tool module in the same folder (see upstream YAML examples). Run with `praisonai agents.yaml`.

## Agent Skills layout

```
pdf-processing/
├── SKILL.md          # required
└── scripts/          # optional helpers
```

`SKILL.md` frontmatter (Agent Skills standard):

```yaml
---
name: pdf-processing
description: Process PDFs. Use when the user asks to read or extract PDF data.
license: Apache-2.0
compatibility: Works with PraisonAI Agents
metadata:
  author: praisonai
  version: "1.0"
---
```

Discover / attach:

```python
from praisonaiagents import Agent, SkillManager

manager = SkillManager()
manager.discover(["./pdf-processing"], include_defaults=False)

agent = Agent(
    instructions="You process PDFs.",
    skills=["./pdf-processing"],
)
```

CLI scaffold:

```bash
praisonai skills create \
  --name csv-analyzer \
  --description "Analyze CSV files" \
  --template \
  --script \
  --output-dir ./skills
```

## JS SDK (minimal)

```bash
npm install praisonai
```

Mirror Python patterns via the TypeScript package; see upstream `src/praisonai-ts/` and `examples/js/`.

## Upstream example map

When unsure, copy from upstream `examples/`:

| Area | Path |
|------|------|
| Skills | `examples/skills/` |
| MCP | `examples/mcp/`, `examples/mcp_server/` |
| Multi-agent | `examples/multi_agent/` |
| Workflows | `examples/workflows/` |
| RAG / knowledge | `examples/rag/`, `examples/knowledge/` |
| Guardrails | `examples/guardrails/` |
| YAML | `examples/yaml/` |
| Providers | `examples/python/providers/` |
