"""Repeated-measure review-artifact tests for anno-lab raw exports."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from label_lab.adjudication import (
    build_anno_lab_raw_canonical_record_import_artifact,
    emit_anno_lab_raw_canonical_record_import_artifact,
    emit_anno_lab_raw_review_artifact,
)
from label_lab.sources.anno_lab_raw import build_anno_lab_raw_review_artifact

FIXTURES_ROOT = Path(__file__).parent / "fixtures"
SOURCE_ANNO_LAB_RAW_REPEATED_FIXTURE = (
    FIXTURES_ROOT / "demo_anno_lab_raw_repeated_measure_export.json"
)
REVIEW_ADJUDICATION_FIXTURE = FIXTURES_ROOT / "demo_anno_lab_raw_review_adjudication.json"


def test_build_review_artifact_groups_repeated_measure_candidates() -> None:
    artifact = build_anno_lab_raw_review_artifact(SOURCE_ANNO_LAB_RAW_REPEATED_FIXTURE)

    assert artifact["artifact_kind"] == "anno_lab_raw_review_groups"
    assert artifact["artifact_version"] == "1.0.0"
    assert artifact["normalization_profile"] == "anno_lab_repeated_measure_review_v1"
    assert artifact["summary"] == {
        "annotation_record_count": 3,
        "asset_count": 2,
        "assignment_count": 3,
        "review_annotation_count": 2,
        "review_group_count": 1,
        "single_annotation_task_count": 1,
        "task_count": 2,
    }
    review_group = artifact["review_groups"][0]
    assert review_group["group_id"] == "task-501"
    assert review_group["annotation_count"] == 2
    assert review_group["asset"]["file_name"] == "slide_001.jpg"
    assert review_group["candidate_annotations"][0]["assignment_status"] == "submitted"
    assert review_group["candidate_annotations"][1]["assignment_status"] == "approved"
    assert "worker-redacted" not in json.dumps(artifact)


def test_emit_review_artifact_writes_json_summary(tmp_path: Path) -> None:
    artifact_path = tmp_path / "review-groups.json"

    summary = emit_anno_lab_raw_review_artifact(
        source_path=SOURCE_ANNO_LAB_RAW_REPEATED_FIXTURE,
        output_path=artifact_path,
    )

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert summary == {
        "artifact_kind": "anno_lab_raw_review_groups",
        "artifact_path": str(artifact_path.resolve()),
        "artifact_version": "1.0.0",
        "review_annotation_count": 2,
        "review_group_count": 1,
        "single_annotation_task_count": 1,
    }
    assert artifact["summary"]["review_group_count"] == 1
    assert artifact["review_groups"][0]["task_id"] == "501"


def test_build_canonical_record_import_artifact_from_review_groups(
    tmp_path: Path,
) -> None:
    review_path = tmp_path / "review-groups.json"
    emit_anno_lab_raw_review_artifact(
        source_path=SOURCE_ANNO_LAB_RAW_REPEATED_FIXTURE,
        output_path=review_path,
    )

    artifact = build_anno_lab_raw_canonical_record_import_artifact(
        review_groups_path=review_path,
        adjudication_path=REVIEW_ADJUDICATION_FIXTURE,
    )

    assert artifact["artifact_kind"] == "anno_lab_raw_canonical_record_import"
    assert artifact["artifact_version"] == "1.0.0"
    assert artifact["normalization_profile"] == (
        "anno_lab_repeated_measure_canonical_record_import_v1"
    )
    assert artifact["summary"] == {
        "review_group_count": 1,
        "canonical_record_count": 1,
        "single_annotation_task_count": 1,
    }
    canonical_record = artifact["canonical_records"][0]
    assert canonical_record["group_id"] == "task-501"
    assert canonical_record["selected_annotation"]["annotation_id"] == "703"
    assert canonical_record["selected_annotation"]["assignment_status"] == "approved"
    assert canonical_record["adjudication"]["adjudicator_id"] == "reviewer-redacted-001"


def test_emit_canonical_record_import_writes_json_summary(tmp_path: Path) -> None:
    review_path = tmp_path / "review-groups.json"
    canonical_records_path = tmp_path / "canonical-records.json"
    emit_anno_lab_raw_review_artifact(
        source_path=SOURCE_ANNO_LAB_RAW_REPEATED_FIXTURE,
        output_path=review_path,
    )

    summary = emit_anno_lab_raw_canonical_record_import_artifact(
        review_groups_path=review_path,
        adjudication_path=REVIEW_ADJUDICATION_FIXTURE,
        output_path=canonical_records_path,
    )

    artifact = json.loads(canonical_records_path.read_text(encoding="utf-8"))
    assert summary == {
        "artifact_kind": "anno_lab_raw_canonical_record_import",
        "artifact_path": str(canonical_records_path.resolve()),
        "artifact_version": "1.0.0",
        "review_group_count": 1,
        "canonical_record_count": 1,
        "single_annotation_task_count": 1,
    }
    assert artifact["canonical_records"][0]["selected_annotation"]["annotation_id"] == "703"


def test_build_canonical_record_import_rejects_missing_group_decision(
    tmp_path: Path,
) -> None:
    review_path = tmp_path / "review-groups.json"
    adjudication_path = tmp_path / "decisions.json"
    emit_anno_lab_raw_review_artifact(
        source_path=SOURCE_ANNO_LAB_RAW_REPEATED_FIXTURE,
        output_path=review_path,
    )
    adjudication_path.write_text(
        json.dumps(
            {
                "artifact_kind": "anno_lab_raw_review_adjudication",
                "artifact_version": "1.0.0",
                "source_artifact_kind": "anno_lab_raw_review_groups",
                "source_artifact_version": "1.0.0",
                "source_export": {
                    "source_artifact": "demo_anno_lab_raw_repeated_measure_export.json",
                    "source_project_id": "101",
                    "source_project_slug": "anno-lab-raw-demo",
                    "source_project_name": "Anno Lab Raw Demo",
                },
                "decisions": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing adjudication decision for review group"):
        build_anno_lab_raw_canonical_record_import_artifact(
            review_groups_path=review_path,
            adjudication_path=adjudication_path,
        )


def test_build_canonical_record_import_rejects_mismatched_source_export(
    tmp_path: Path,
) -> None:
    review_path = tmp_path / "review-groups.json"
    adjudication_path = tmp_path / "decisions.json"
    emit_anno_lab_raw_review_artifact(
        source_path=SOURCE_ANNO_LAB_RAW_REPEATED_FIXTURE,
        output_path=review_path,
    )
    adjudication_payload = json.loads(REVIEW_ADJUDICATION_FIXTURE.read_text(encoding="utf-8"))
    adjudication_payload["source_export"]["source_project_slug"] = "wrong-project"
    adjudication_path.write_text(
        json.dumps(adjudication_payload),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="adjudication source_export.source_project_slug does not match review artifact",
    ):
        build_anno_lab_raw_canonical_record_import_artifact(
            review_groups_path=review_path,
            adjudication_path=adjudication_path,
        )
