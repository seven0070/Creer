# Creer

Cursor Agent Skills collection. Skills here are meant for **global** (user-level) install.

## Skills

| Skill | Description |
|-------|-------------|
| [praisonai](skills/praisonai/) | Build PraisonAI agents, multi-agent teams, MCP tools, YAML workflows, and Agent Skills |

## Install globally

Copy a skill into your user skills directory so it applies across all projects:

```bash
mkdir -p ~/.cursor/skills
cp -R skills/praisonai ~/.cursor/skills/
```

Or symlink:

```bash
mkdir -p ~/.cursor/skills
ln -s "$(pwd)/skills/praisonai" ~/.cursor/skills/praisonai
```

Then invoke with `/praisonai` or `@praisonai` in Agent chat.

You can also install via **Customize → Rules → Add Rule → Remote Rule (Github)** pointing at this repository.

Skill format follows the [Agent Skills](https://agentskills.io) standard.

Source material for the PraisonAI skill: [MervinPraison/PraisonAI](https://github.com/MervinPraison/PraisonAI).
