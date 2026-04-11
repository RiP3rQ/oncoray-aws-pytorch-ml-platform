# Implementation Plan: ML Project Setup for ViT + EffNetB2

## Problem

`uv add --active pytorch` fails because root `pyproject.toml` only has `[tool.uv.workspace]` — no `[project]` table.
`uv add` requires a `[project]` table to manage production dependencies.

## Decisions

| # | Question                   | Decision                                                                            |
|---|----------------------------|-------------------------------------------------------------------------------------|
| 1 | Root `pyproject.toml` role | **Root-as-package** — add `[project]` table so `uv add` works at root level         |
| 2 | Model package layout       | **Single package** — both ViT and EffNetB2 in one `optic-models` package            |
| 3 | Package name               | **`optic-models`** / Python module `optic_models`                                   |
| 4 | Dependencies location      | **Shared at root** — torch, numpy, matplotlib, torchvision in root `pyproject.toml` |
| 5 | Existing `first-model`     | **Remove** `model/` directory entirely                                              |
| 6 | Module structure           | **Flat** — `optic_models/vit.py`, `optic_models/effnet.py`                          |
| 7 | CLI entry points           | **None** — run via `uv run python -m optic_models.vit`                              |
| 8 | Python version             | **3.11** (keep current `.python-version`)                                           |

## Current State

```
pytorch-engine/
├── .gitignore
├── .python-version          # 3.11
├── .venv/
├── model/                    # REMOVE
│   ├── pyproject.toml        # name="first-model", depends on torch
│   └── src/first_model/
│       ├── __init__.py
│       ├── __pycache__/
│       └── train.py          # simple linear regression trainer
├── package.json              # scripts reference "first-model"
├── pyproject.toml            # ONLY [tool.uv.workspace] — no [project]
└── uv.lock
```

### Root `pyproject.toml` (current)

```toml
[tool.uv.workspace]
members = ["model"]
```

### `model/pyproject.toml` (current)

```toml
[project]
name = "first-model"
version = "0.1.0"
description = "Our first PyTorch model inside the monorepo."
readme = "../README.md"
requires-python = ">=3.11"
dependencies = [
    "torch>=2.6,<3",
]

[project.scripts]
train-model = "first_model.train:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### `package.json` (current)

```json
{
  "name": "pytorch-engine",
  "private": true,
  "scripts": {
    "build": "uv sync",
    "check-types": "uv run --package first-model python -m compileall model/src",
    "train": "uv run --package first-model train-model"
  }
}
```

## Target State

```
pytorch-engine/
├── .gitignore
├── .python-version              # 3.11 (unchanged)
├── .venv/
├── optic-models/                # NEW workspace member
│   ├── pyproject.toml           # minimal, no deps (deps live at root)
│   └── src/optic_models/
│       ├── __init__.py
│       ├── vit.py               # placeholder for ViT model
│       └── effnet.py            # placeholder for EffNetB2 model
├── package.json                 # updated scripts
├── pyproject.toml               # [project] + [tool.uv.workspace]
└── uv.lock                      # regenerated
```

## Implementation Steps

### Step 1: Update root `pyproject.toml`

Add `[project]` table with shared ML dependencies. Keep `[tool.uv.workspace]` pointing to `optic-models/`.

**Target content:**

```toml
[project]
name = "pytorch-engine"
version = "0.1.0"
description = "ML project for ViT and EffNetB2 optic models."
requires-python = ">=3.11"
dependencies = [
    "torch>=2.6,<3",
    "torchvision>=0.21,<1",
    "numpy>=2,<3",
    "matplotlib>=3.9,<4",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.uv.workspace]
members = ["optic-models"]
```

**Rationale:**

- `torch`, `torchvision`, `numpy`, `matplotlib` at root — shared across all workspace members
- Version pins: torch 2.6+ for modern APIs, torchvision matches torch compatibility, numpy 2.x for current API,
  matplotlib 3.9+ for style features
- Workspace members updated from `["model"]` to `["optic-models"]`

### Step 2: Delete `model/` directory

Remove the entire `model/` directory and its contents (`first-model` package). Decision: remove, not keep.

```
rm -rf model/
```

### Step 3: Create `optic-models/` workspace member

**`optic-models/pyproject.toml`:**

```toml
[project]
name = "optic-models"
version = "0.1.0"
description = "ViT and EfficientNet-B2 optic models."
requires-python = ">=3.11"
dependencies = []

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**Rationale:**

- No package-level dependencies — all deps live at root
- Empty `dependencies = []` is explicit: this package uses root workspace deps

**`optic-models/src/optic_models/__init__.py`:**

```python
from __future__ import annotations
```

**`optic-models/src/optic_models/vit.py`:**

```python
from __future__ import annotations

# ViT optic model — implementation TBD
```

**`optic-models/src/optic_models/effnet.py`:**

```python
from __future__ import annotations

# EffNetB2 optic model — implementation TBD
```

**Rationale:**

- Flat module layout per decision (no sub-packages)
- Placeholder stubs — scope is project setup only, not model implementation
- `from __future__ import annotations` follows existing pattern from `first-model/train.py`

### Step 4: Update `package.json` scripts

Replace `first-model` references with `optic-models` commands.

**Target content:**

```json
{
  "name": "pytorch-engine",
  "private": true,
  "scripts": {
    "build": "uv sync",
    "check-types": "uv run --package optic-models python -m compileall optic-models/src",
    "train-vit": "uv run --package optic-models python -m optic_models.vit",
    "train-effnet": "uv run --package optic-models python -m optic_models.effnet"
  }
}
```

**Rationale:**

- `build` unchanged — `uv sync` still resolves all deps
- `check-types` updated — points to `optic-models/src`
- No CLI entry points per decision — use `python -m` pattern
- `train-vit` and `train-effnet` as Turborepo-accessible scripts

### Step 5: Delete `uv.lock` and regenerate

Old lock file references `first-model`. Must regenerate.

```powershell
del uv.lock
uv sync
```

**Rationale:** Lock file contains `first-model` package entries. Clean regeneration avoids stale references.

### Step 6: Verify setup

```powershell
# Verify packages resolve
uv sync

# Verify Python can import
uv run --package optic-models python -c "import optic_models; print('OK')"

# Verify torch imports (from root deps)
uv run --package optic-models python -c "import torch; print(torch.__version__)"

# Verify torchvision imports
uv run --package optic-models python -c "import torchvision; print(torchvision.__version__)"
```

## Notes

- **Hatchling build backend**: Matches existing pattern from `first-model`. Consistent within workspace.
- **No `.venv` changes needed**: `uv sync` recreates venv automatically.
- **Turborepo integration**: Root `package.json` scripts are callable via `turbo run` from monorepo root (
  `D:\Pytorch-model`).
- **CUDA note**: If GPU support needed, torch must be installed with CUDA index URL. Default `torch` from PyPI is
  CPU-only. Check `uv` docs for `[[tool.uv.index]]` configuration if CUDA wheels required.
