"""tests/test_tokens.py — unit tests for the token registration and formatting system.

These tests run without Blender.  ``lib/tokens.py`` has no ``bpy`` dependency.
"""

from lib import tokens


def setup_function():
    """Clear all registered tokens before each test to ensure isolation."""
    tokens._registered_tokens.clear()


def test_register_and_format():
    tokens.register_token("<foo>", lambda opts: "bar", label="Foo")
    assert tokens.format_tokens("<foo>_suffix", None) == "bar_suffix"


def test_format_multiple_tokens():
    tokens.register_token("<proj>", lambda opts: "MyProject")
    tokens.register_token("<task>", lambda opts: "animation")
    result = tokens.format_tokens("<proj>_<task>_v01", None)
    assert result == "MyProject_animation_v01"


def test_format_with_no_tokens_unchanged():
    assert tokens.format_tokens("plain_name", None) == "plain_name"


def test_format_empty_string_returns_empty():
    assert tokens.format_tokens("", None) == ""


def test_format_none_returns_none():
    assert tokens.format_tokens(None, None) is None


def test_token_assertion_requires_angle_brackets():
    import pytest
    with pytest.raises(AssertionError):
        tokens.register_token("no_brackets", lambda o: "x")


def test_token_assertion_requires_closing_bracket():
    import pytest
    with pytest.raises(AssertionError):
        tokens.register_token("<unclosed", lambda o: "x")


def test_token_func_must_be_callable():
    import pytest
    with pytest.raises(AssertionError):
        tokens.register_token("<bad>", "not_callable")


def test_list_tokens_returns_copy():
    tokens.register_token("<x>", lambda o: "x")
    listed = tokens.list_tokens()
    listed.clear()
    # The original dict is unaffected because list_tokens returns a copy
    assert "<x>" in tokens._registered_tokens


def test_token_lambda_receives_options():
    captured = []
    tokens.register_token("<opt>", lambda opts: captured.append(opts) or "val")
    sentinel = object()
    tokens.format_tokens("<opt>", sentinel)
    assert captured == [sentinel]


def test_unknown_token_left_in_string():
    tokens.register_token("<known>", lambda opts: "K")
    result = tokens.format_tokens("<known>_<unknown>", None)
    assert result == "K_<unknown>"
