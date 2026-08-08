# Creer

Cursor Agent Skills collection.

## Skills

| Skill | Description |
|-------|-------------|
| [praisonai](skills/praisonai/) | Build PraisonAI agents, multi-agent teams, MCP tools, YAML workflows, and Agent Skills |

## How to load the skill

Cursor discovers skills from these locations:

| Location | Scope |
|----------|-------|
| `.cursor/skills/` | This project (auto-loaded when Creer is open) |
| `~/.cursor/skills/` | Global — all projects on your machine |

### Option A — Global (recommended)

Copy once; works in every project:

```bash
mkdir -p ~/.cursor/skills
cp -R skills/praisonai ~/.cursor/skills/
```

Restart Cursor or start a **new Agent chat**, then type `/praisonai` or `@praisonai`.

### Option B — Project-only

Open this repo in Cursor. The skill is at `.cursor/skills/praisonai/` and loads automatically for this workspace.

### Option C — GitHub remote rule

**Customize → Rules → Add Rule → Remote Rule (Github)** → `https://github.com/seven0070/Creer`

**Important:** the skill must exist on the branch you sync from. Merge [PR #1](https://github.com/seven0070/Creer/pull/1) into `main` first, or point the remote rule at branch `cursor/praisonai-skill-5310` until merged.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `/praisonai` not found | Copy to `~/.cursor/skills/` (Option A) or open this repo (Option B) |
| GitHub remote rule empty | Merge PR #1 to `main`, or use the feature branch |
| Skill not in current chat | Start a **new** Agent chat after installing |
| Only works on cloud VM | Global install is per-machine — run the `cp` command on **your** computer |

Skill format: [Agent Skills](https://agentskills.io) standard.

Source: [MervinPraison/PraisonAI](https://github.com/MervinPraison/PraisonAI).
