import json

import pytest

from update_page_metadata import changes_for, merge_manifest


def test_only_page_metadata_can_change():
    rows = [{
        "chunk_id": "book:00001",
        "text": "texte identique",
        "page_start": "4",
        "page_end": "4",
    }]
    chunks = {"book:00001": {
        "chunk_id": "book:00001",
        "text": "texte identique",
        "page_start": 5,
        "page_end": 6,
    }}

    assert changes_for(rows, chunks) == [{
        "chunk_id": "book:00001",
        "before": ("4", "4"),
        "after": ("5", "6"),
    }]


def test_text_change_requires_reembedding():
    rows = [{
        "chunk_id": "book:00001",
        "text": "ancien",
        "page_start": "4",
        "page_end": "4",
    }]
    chunks = {"book:00001": {
        "chunk_id": "book:00001",
        "text": "nouveau",
        "page_start": 4,
        "page_end": 4,
    }}

    with pytest.raises(ValueError, match="re-embedding requis"):
        changes_for(rows, chunks)


def test_manifest_keeps_filter_proof_and_converts_legacy_report(tmp_path):
    chunks = tmp_path / "chunks.jsonl"
    chunks.write_text('{"chunk_id":"book:1"}\n')
    exclusions = tmp_path / "excluded.txt"
    exclusions.write_text("book:2\tbibliographie\n")
    legacy_change = {
        "chunk_id": "book:1",
        "before": ["4", "4"],
        "after": ["5", "5"],
    }
    result = merge_manifest(
        {
            "schema_version": 1,
            "created_at": "2026-07-31T12:00:00+00:00",
            "metadata_only_migration": True,
            "page_ranges_updated": 1,
            "changes": [legacy_change],
        },
        table_name="bunge_512",
        size="512",
        chunks_path=chunks,
        exclusions_path=exclusions,
        chunk_count=2,
        row_count=1,
        excluded_count=1,
        changes=[],
        applied_at="2026-07-31T13:00:00+00:00",
    )

    assert result["filtered"] is True
    assert result["rows_before_filtering"] == 2
    assert result["rows_after_filtering"] == 1
    assert result["excluded_chunks"] == 1
    assert result["exclusions_sha256"]
    assert result["metadata_migrations"][0]["changes"] == [legacy_change]
    assert "metadata_only_migration" not in result
    assert "changes" not in result
    json.dumps(result)
