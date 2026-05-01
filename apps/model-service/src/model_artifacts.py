from __future__ import annotations

from pathlib import Path
from typing import Any

import torch


def load_state_dict(artifact_path: Path, map_location: torch.device) -> dict[str, Any]:
    payload = torch.load(artifact_path, map_location=map_location)
    if isinstance(payload, dict):
        if any(isinstance(value, torch.Tensor) for value in payload.values()):
            return payload

        for key in ("state_dict", "model_state_dict", "model"):
            nested = payload.get(key)
            if isinstance(nested, dict):
                return nested

    raise TypeError(f"Unsupported model artifact payload at {artifact_path}")
