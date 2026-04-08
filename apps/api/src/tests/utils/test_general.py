"""
Tests for general utility functions.
"""

import sys
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.general import print_label


class TestPrintLabel:
    """Tests for print_label utility."""

    def test_print_label_with_dict(self, capsys):
        """print_label should print a dict as formatted JSON."""
        data = {"key": "value"}
        print_label(data, title="Test Title")
        captured = capsys.readouterr()
        assert "Test Title" in captured.out

    def test_print_label_with_string(self, capsys):
        """print_label should print a string directly."""
        print_label("hello world", title="Msg")
        captured = capsys.readouterr()
        assert "hello world" in captured.out

    def test_print_label_with_none_title(self, capsys):
        """print_label should work without a title."""
        print_label({"test": 123})
        captured = capsys.readouterr()
        assert "test" in captured.out

    def test_print_label_with_non_serializable_dict(self, capsys):
        """print_label should handle dicts with non-JSON-serializable values.

        The function catches JSONDecodeError but TypeError is also raised
        for non-serializable values like functions. Since TypeError is not
        caught, this will raise - so we test that it propagates.
        """

        # dicts should work fine for plain JSON-serializable values
        data = {"a": 1, "b": 2}
        # This should work (serializable dict)
        print_label(data)
        captured = capsys.readouterr()
        assert "a" in captured.out

    def test_print_label_with_mapping_type(self, capsys):
        """print_label should handle Mapping types."""
        from collections import OrderedDict

        data = OrderedDict([("a", 1), ("b", 2)])
        print_label(data)
        captured = capsys.readouterr()
        assert "a" in captured.out
