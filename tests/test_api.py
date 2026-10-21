"""Unit tests for URL building."""

from custom_components.photoframe.api import _segment


def test_segment_turns_slash_into_plus() -> None:
    # The frame turns '+' back into '/' for timezone.
    assert _segment("America/New_York") == "America+New_York"


def test_segment_escapes_reserved_characters() -> None:
    assert _segment("a b?c#d") == "a%20b%3Fc%23d"
    assert _segment(1) == "1"
