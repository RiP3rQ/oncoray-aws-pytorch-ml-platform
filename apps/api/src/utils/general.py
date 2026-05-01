from collections.abc import Mapping
from contextlib import suppress
from json import JSONDecodeError, dumps
from typing import Any

from rich import print
from rich.panel import Panel


def print_label(data: Any, title: str | None = None) -> None:
    """
    Print a label with the data.
    """
    with suppress(JSONDecodeError):
        data = dumps(data, indent=4) if isinstance(data, (dict, Mapping)) else data

    print()
    print(
        Panel(
            data,
            title=title,
        ),
        end="\n\n",
    )
