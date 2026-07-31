import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from push_space import build_space_bundle, stale_remote_files  # noqa: E402


def test_public_bundle_is_strictly_allowlisted(tmp_path):
    copied = build_space_bundle(tmp_path)
    files = {
        str(path.relative_to(tmp_path))
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    assert files == set(copied)
    forbidden = {".env", "corpus", "eval", "index", "chunks", "HF_WRITE_TOKEN"}
    assert not any(
        any(part in forbidden for part in Path(relative).parts)
        for relative in files
    )
    assert all("WRITE_TOKEN" not in path.read_text(errors="ignore")
               for path in tmp_path.rglob("*") if path.is_file())


def test_remote_space_is_synchronized_to_allowlist():
    copied = ["app.py", "README.md", "src/rag.py"]
    remote = [".gitattributes", *copied, "old_app.py", "debug/context.txt"]
    assert stale_remote_files(remote, copied) == ["debug/context.txt", "old_app.py"]
