import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "space" / "styles.css").read_text(encoding="utf-8")


def test_custom_properties_are_namespaced_for_gradio() -> None:
    declarations = re.findall(r"^\s*(--[a-z0-9-]+)\s*:", CSS, flags=re.MULTILINE)

    assert declarations
    assert all(name.startswith("--bunge-") for name in declarations)
    assert "var(--muted)" not in CSS

