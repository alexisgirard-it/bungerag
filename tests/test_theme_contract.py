import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
THEME_SOURCE = (ROOT / "space" / "theme.py").read_text(encoding="utf-8")


def theme_set_values() -> dict[str, str]:
    tree = ast.parse(THEME_SOURCE)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "set":
                return {
                    keyword.arg: ast.literal_eval(keyword.value)
                    for keyword in node.keywords
                    if keyword.arg is not None
                }
    raise AssertionError("Gradio theme .set() call not found")


def test_editorial_palette_is_identical_in_gradio_dark_mode() -> None:
    theme = theme_set_values()
    fixed_tokens = (
        "body_background_fill",
        "body_text_color",
        "body_text_color_subdued",
        "background_fill_primary",
        "background_fill_secondary",
        "border_color_primary",
        "block_background_fill",
        "block_border_color",
        "block_label_background_fill",
        "block_label_text_color",
        "block_title_text_color",
        "input_background_fill",
        "input_border_color",
        "input_placeholder_color",
        "button_primary_background_fill",
        "button_primary_background_fill_hover",
        "button_primary_text_color",
        "button_secondary_background_fill",
        "button_secondary_background_fill_hover",
        "button_secondary_text_color",
    )

    assert all(theme[token] == theme[f"{token}_dark"] for token in fixed_tokens)
