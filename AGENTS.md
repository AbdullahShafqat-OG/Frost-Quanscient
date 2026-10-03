# AGENTS.md

Guidance for AI coding agents working in this repository.

## Context

Read `README.md` first, then `backend/README.md` or `frontend/README.md` for the part you're working on. They cover setup, running, the API and project structure.

## Skills

Before writing or changing anything that touches the Allsolve SDK or the simulation script (`backend/app/allsolve/`, `backend/sim/`), read the relevant skill in `sdk-skills/`:

- Start with `sdk-skills/allsolve-sdk/SKILL.md` — the main entry point; it links to the sub-skills.
- Most relevant here: `allsolve-domain-thermal` and `allsolve-simulation-scripts`.

Follow the skills' guidance rather than guessing SDK APIs.

## Conventions

- Keep changes small and match the style of the surrounding code.
- Never commit credentials; configuration comes from environment variables (`backend/app/config.py`).
- Don't edit files in `sdk-skills/` unless the task is specifically about updating skills (see `sdk-skills/allsolve-skill-update/SKILL.md`).
