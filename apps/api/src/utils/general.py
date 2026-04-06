from json import JSONDecodeError, dumps
from typing import Any, Mapping
from rich import print
from rich.panel import Panel


def print_label(data: Any, title: str | None = None):
    """
    Print a label with the data.
    """
    try:
        data = dumps(data, indent=4) if isinstance(data, (dict, Mapping)) else data
    except JSONDecodeError:
        pass

    print()
    print(
        Panel(
            data,
            title=title,
        ),
        end="\n\n",
    )
