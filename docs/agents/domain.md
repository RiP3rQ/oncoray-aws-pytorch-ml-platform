# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Layout

This repo uses a single-context layout.

Expected locations:

- `CONTEXT.md` at the repo root
- `docs/adr/` for architectural decision records

## Before exploring, read these

- `CONTEXT.md` at the repo root, if it exists.
- `docs/adr/` ADRs that touch the area about to be changed, if they exist.

If any of these files do not exist, proceed silently. Do not flag their absence or suggest creating them upfront. Producer skills such as `grill-with-docs` create them lazily when terms or decisions get resolved.

## Use the glossary's vocabulary

When output names a domain concept, such as in an issue title, refactor proposal, hypothesis, or test name, use the term as defined in `CONTEXT.md`.

If the concept needed is not in the glossary yet, either reconsider the term or note the gap for `grill-with-docs`.

## Flag ADR conflicts

If output contradicts an existing ADR, surface it explicitly rather than silently overriding it.
