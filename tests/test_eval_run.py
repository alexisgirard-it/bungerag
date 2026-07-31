import json
from dataclasses import replace

import pytest

from config import PUBLIC_V1
from eval_run import (
    build_metadata,
    is_strict_abstention,
    prepare_run,
    validate_references,
)


RUNTIME = {
    "pipeline_entrypoint": "ask_smart",
    "generation": {"backend": "gemini", "models": ["model-a"]},
    "translation": {"backend": "cerebras", "model": "utility"},
    "routing": {"backend": "cerebras", "model": "utility"},
    "judge": {"provider": "cerebras", "model": "judge"},
    "evaluation": {"ragas_version": "0.4.3", "metrics": ["faithfulness"]},
}


def questions(status="verifiee-corpus"):
    return [
        {
            "id": 1,
            "type": "contenu",
            "question": "Q ?",
            "reference": "R.",
            "reference_status": status,
        },
        {"id": 31, "type": "piege", "question": "P ?", "reference": "Absent."},
    ]


def write_fixture_repo(tmp_path, status="verifiee-corpus"):
    (tmp_path / "src").mkdir()
    for name in (
        "config.py", "search.py", "rerank.py", "retrieve.py", "decompose.py",
        "rag.py", "generate.py", "citations.py", "schemas.py", "output_guard.py",
        "eval_run.py", "eval_ragas.py",
    ):
        (tmp_path / "src" / name).write_text(name)
    (tmp_path / "requirements.txt").write_text("ragas==0.4.3\n")
    index = tmp_path / "index"
    index.mkdir()
    (index / "manifest-bunge_512.json").write_text(json.dumps({
        "table": "bunge_512",
        "chunk_sha256": "chunks-v1",
        "rows_after_filtering": 10,
        "embedding_model": "embedding",
        "embedding_revision": "revision",
        "filtered": True,
        "exclusions_sha256": "exclusions-v1",
    }))
    path = tmp_path / "questions.jsonl"
    path.write_text("\n".join(json.dumps(item) for item in questions(status)) + "\n")
    return path


def test_unvalidated_reference_blocks_public_run():
    with pytest.raises(ValueError, match="q01"):
        validate_references(questions("corrigee-a-valider"))


def test_fingerprint_changes_with_config_or_prompt(tmp_path):
    path = write_fixture_repo(tmp_path)
    common = {
        "root": tmp_path,
        "questions_path": path,
        "index_manifest_path": tmp_path / "index" / "manifest-bunge_512.json",
        "runtime_identity": RUNTIME,
    }
    first = build_metadata(
        config=PUBLIC_V1, system_prompt="v1", **common
    )
    changed_config = build_metadata(
        config=replace(PUBLIC_V1, k_final=4),
        system_prompt="v1",
        **common,
    )
    changed_prompt = build_metadata(
        config=PUBLIC_V1, system_prompt="v2", **common
    )
    changed_runtime = build_metadata(
        config=PUBLIC_V1,
        system_prompt="v1",
        runtime_identity={**RUNTIME, "pipeline_entrypoint": "ask"},
        **{key: value for key, value in common.items() if key != "runtime_identity"},
    )

    assert first["run_id"] != changed_config["run_id"]
    assert first["run_id"] != changed_prompt["run_id"]
    assert first["run_id"] != changed_runtime["run_id"]
    assert "secret" not in json.dumps(first).lower()


def test_same_run_reuses_matching_metadata(tmp_path):
    path = write_fixture_repo(tmp_path)
    kwargs = dict(
        root=tmp_path,
        cache_root=tmp_path / "cache",
        config=PUBLIC_V1,
        questions_path=path,
        system_prompt="v1",
        index_manifest_path=tmp_path / "index" / "manifest-bunge_512.json",
        runtime_identity=RUNTIME,
    )
    run_dir, first = prepare_run(**kwargs)
    same_dir, second = prepare_run(**kwargs)

    assert run_dir == same_dir
    assert first == second


def test_index_change_gets_a_distinct_run(tmp_path):
    path = write_fixture_repo(tmp_path)
    manifest = tmp_path / "index" / "manifest-bunge_512.json"
    kwargs = dict(
        root=tmp_path,
        config=PUBLIC_V1,
        questions_path=path,
        system_prompt="v1",
        index_manifest_path=manifest,
        runtime_identity=RUNTIME,
    )
    first = build_metadata(**kwargs)
    data = json.loads(manifest.read_text())
    data["chunk_sha256"] = "chunks-v2"
    manifest.write_text(json.dumps(data))
    second = build_metadata(**kwargs)
    assert first["run_id"] != second["run_id"]


def test_only_corpus_refusals_count_as_strict_abstentions():
    assert is_strict_abstention("pre-generation")
    assert is_strict_abstention("llm")
    assert not is_strict_abstention("citation-validation")
    assert not is_strict_abstention("output-validation")
