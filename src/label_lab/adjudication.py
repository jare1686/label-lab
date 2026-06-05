"""Adjudication-review artifact emission for repeated-measure source inputs.

Repeated-measure ``anno_lab_raw`` exports are intentionally kept out of the
direct release path until they are adjudicated down to one canonical annotation
record per task. This module materializes explicit intermediate artifacts:
review groups and adjudicated canonical-record imports.
"""

from __future__ import annotations

import json
from pathlib import Path

from label_lab.sources.anno_lab_raw import (
    ANNO_LAB_RAW_EXPORT_CONTRACT,
    ANNO_LAB_RAW_EXPORT_VERSION,
    ANNO_LAB_REVIEW_GROUPS_ARTIFACT_KIND,
    ANNO_LAB_REVIEW_GROUPS_ARTIFACT_VERSION,
    build_anno_lab_raw_review_artifact,
)
from label_lab.sources.validation import (
    coerce_int,
    load_json_object,
    normalize_optional_string,
    require_identifier,
    require_non_empty_string,
    require_object,
    require_object_list,
)

ANNO_LAB_REVIEW_ADJUDICATION_ARTIFACT_KIND = "anno_lab_raw_review_adjudication"
ANNO_LAB_REVIEW_ADJUDICATION_ARTIFACT_VERSION = "1.0.0"
ANNO_LAB_CANONICAL_RECORD_IMPORT_ARTIFACT_KIND = "anno_lab_raw_canonical_record_import"
ANNO_LAB_CANONICAL_RECORD_IMPORT_ARTIFACT_VERSION = "1.0.0"
ANNO_LAB_CANONICAL_RECORD_IMPORT_PROFILE = (
    "anno_lab_repeated_measure_canonical_record_import_v1"
)


def emit_anno_lab_raw_review_artifact(
    *,
    source_path: str | Path,
    output_path: str | Path,
) -> dict[str, object]:
    """Write a repeated-measure review artifact for an ``anno_lab_raw`` export."""
    artifact = build_anno_lab_raw_review_artifact(source_path)
    resolved_output_path = Path(output_path).resolve()
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_output_path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = require_object(artifact.get("summary"), "summary")

    return {
        "artifact_path": str(resolved_output_path),
        "artifact_kind": require_non_empty_string(
            artifact.get("artifact_kind"),
            "artifact_kind",
        ),
        "artifact_version": require_non_empty_string(
            artifact.get("artifact_version"),
            "artifact_version",
        ),
        "review_group_count": coerce_int(
            summary.get("review_group_count"),
            "summary.review_group_count",
        ),
        "review_annotation_count": coerce_int(
            summary.get("review_annotation_count"),
            "summary.review_annotation_count",
        ),
        "single_annotation_task_count": coerce_int(
            summary.get("single_annotation_task_count"),
            "summary.single_annotation_task_count",
        ),
    }


def emit_anno_lab_raw_canonical_record_import_artifact(
    *,
    review_groups_path: str | Path,
    adjudication_path: str | Path,
    output_path: str | Path,
) -> dict[str, object]:
    """Write an adjudicated canonical-record import artifact from review groups."""
    artifact = build_anno_lab_raw_canonical_record_import_artifact(
        review_groups_path=review_groups_path,
        adjudication_path=adjudication_path,
    )
    resolved_output_path = Path(output_path).resolve()
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_output_path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = require_object(artifact.get("summary"), "summary")
    return {
        "artifact_path": str(resolved_output_path),
        "artifact_kind": require_non_empty_string(
            artifact.get("artifact_kind"),
            "artifact_kind",
        ),
        "artifact_version": require_non_empty_string(
            artifact.get("artifact_version"),
            "artifact_version",
        ),
        "review_group_count": coerce_int(
            summary.get("review_group_count"),
            "summary.review_group_count",
        ),
        "canonical_record_count": coerce_int(
            summary.get("canonical_record_count"),
            "summary.canonical_record_count",
        ),
        "single_annotation_task_count": coerce_int(
            summary.get("single_annotation_task_count"),
            "summary.single_annotation_task_count",
        ),
    }


def build_anno_lab_raw_canonical_record_import_artifact(
    *,
    review_groups_path: str | Path,
    adjudication_path: str | Path,
) -> dict[str, object]:
    """Build a canonical-record import artifact from adjudicated review groups."""
    resolved_review_groups_path = Path(review_groups_path).resolve()
    review_artifact = load_json_object(resolved_review_groups_path)
    _validate_review_groups_artifact(review_artifact)
    source_export = require_object(review_artifact.get("source_export"), "source_export")
    review_summary = require_object(review_artifact.get("summary"), "summary")
    review_groups = require_object_list(review_artifact, "review_groups")

    resolved_adjudication_path = Path(adjudication_path).resolve()
    adjudication_payload = load_json_object(resolved_adjudication_path)
    decisions_by_group = _load_adjudication_decisions(
        adjudication_payload,
        review_artifact=review_artifact,
    )

    canonical_records: list[dict[str, object]] = []
    for index, review_group in enumerate(review_groups):
        context = f"review_groups[{index}]"
        group_id = require_non_empty_string(review_group.get("group_id"), f"{context}.group_id")
        decision = decisions_by_group.pop(group_id, None)
        if decision is None:
            raise ValueError(
                "missing adjudication decision for review group "
                f"{group_id!r}; every review group needs one selected annotation"
            )
        selected_annotation_id = require_identifier(
            decision.get("selected_annotation_id"),
            f"decisions[{group_id!r}].selected_annotation_id",
        )
        candidate_annotations = require_object_list(review_group, "candidate_annotations")
        selected_annotation = _select_candidate_annotation(
            candidate_annotations,
            selected_annotation_id=selected_annotation_id,
            context=context,
        )
        canonical_records.append(
            {
                "canonical_record_id": f"{group_id}:{selected_annotation_id}",
                "group_id": group_id,
                "task_id": require_identifier(review_group.get("task_id"), f"{context}.task_id"),
                "task_definition_id": require_identifier(
                    review_group.get("task_definition_id"),
                    f"{context}.task_definition_id",
                ),
                "task_type": require_non_empty_string(
                    review_group.get("task_type"),
                    f"{context}.task_type",
                ),
                "asset": require_object(review_group.get("asset"), f"{context}.asset"),
                "selected_annotation": selected_annotation,
                "adjudication": {
                    "selected_annotation_id": selected_annotation_id,
                    "adjudicator_id": normalize_optional_string(decision.get("adjudicator_id")),
                    "decided_at": normalize_optional_string(decision.get("decided_at")),
                    "decision_note": normalize_optional_string(decision.get("decision_note")),
                },
            }
        )

    if decisions_by_group:
        unused_group_ids = ", ".join(sorted(decisions_by_group))
        raise ValueError(
            "adjudication decisions reference unknown review groups: "
            f"{unused_group_ids}"
        )

    review_group_count = coerce_int(
        review_summary.get("review_group_count"),
        "summary.review_group_count",
    )
    single_annotation_task_count = coerce_int(
        review_summary.get("single_annotation_task_count"),
        "summary.single_annotation_task_count",
    )

    return {
        "artifact_kind": ANNO_LAB_CANONICAL_RECORD_IMPORT_ARTIFACT_KIND,
        "artifact_version": ANNO_LAB_CANONICAL_RECORD_IMPORT_ARTIFACT_VERSION,
        "source_contract": ANNO_LAB_RAW_EXPORT_CONTRACT,
        "source_contract_version": ANNO_LAB_RAW_EXPORT_VERSION,
        "normalization_profile": ANNO_LAB_CANONICAL_RECORD_IMPORT_PROFILE,
        "source_export": {
            "source_artifact": require_non_empty_string(
                source_export.get("source_artifact"),
                "source_export.source_artifact",
            ),
            "source_project_id": require_identifier(
                source_export.get("source_project_id"),
                "source_export.source_project_id",
            ),
            "source_project_slug": require_non_empty_string(
                source_export.get("source_project_slug"),
                "source_export.source_project_slug",
            ),
            "source_project_name": require_non_empty_string(
                source_export.get("source_project_name"),
                "source_export.source_project_name",
            ),
            "exported_at": normalize_optional_string(source_export.get("exported_at")),
            "review_groups_artifact": resolved_review_groups_path.name,
            "adjudication_artifact": resolved_adjudication_path.name,
        },
        "summary": {
            "review_group_count": review_group_count,
            "canonical_record_count": len(canonical_records),
            "single_annotation_task_count": single_annotation_task_count,
        },
        "canonical_records": canonical_records,
        "notes": [
            (
                "Each canonical record is an adjudicated selection from one "
                "repeated-measure review group."
            ),
            (
                "This artifact is repo-local import scaffolding; it does not "
                "widen the published release bundle contract."
            ),
        ],
    }


def _validate_review_groups_artifact(review_artifact: dict[str, object]) -> None:
    artifact_kind = require_non_empty_string(
        review_artifact.get("artifact_kind"),
        "artifact_kind",
    )
    if artifact_kind != ANNO_LAB_REVIEW_GROUPS_ARTIFACT_KIND:
        raise ValueError(
            "unsupported review artifact kind "
            f"{artifact_kind!r}; expected {ANNO_LAB_REVIEW_GROUPS_ARTIFACT_KIND!r}"
        )
    artifact_version = require_non_empty_string(
        review_artifact.get("artifact_version"),
        "artifact_version",
    )
    if artifact_version != ANNO_LAB_REVIEW_GROUPS_ARTIFACT_VERSION:
        raise ValueError(
            "unsupported review artifact version "
            f"{artifact_version!r}; expected {ANNO_LAB_REVIEW_GROUPS_ARTIFACT_VERSION!r}"
        )


def _load_adjudication_decisions(
    adjudication_payload: dict[str, object],
    *,
    review_artifact: dict[str, object],
) -> dict[str, dict[str, object]]:
    artifact_kind = require_non_empty_string(
        adjudication_payload.get("artifact_kind"),
        "artifact_kind",
    )
    if artifact_kind != ANNO_LAB_REVIEW_ADJUDICATION_ARTIFACT_KIND:
        raise ValueError(
            "unsupported adjudication artifact kind "
            f"{artifact_kind!r}; expected "
            f"{ANNO_LAB_REVIEW_ADJUDICATION_ARTIFACT_KIND!r}"
        )
    artifact_version = require_non_empty_string(
        adjudication_payload.get("artifact_version"),
        "artifact_version",
    )
    if artifact_version != ANNO_LAB_REVIEW_ADJUDICATION_ARTIFACT_VERSION:
        raise ValueError(
            "unsupported adjudication artifact version "
            f"{artifact_version!r}; expected "
            f"{ANNO_LAB_REVIEW_ADJUDICATION_ARTIFACT_VERSION!r}"
        )
    source_artifact_kind = require_non_empty_string(
        adjudication_payload.get("source_artifact_kind"),
        "source_artifact_kind",
    )
    if source_artifact_kind != require_non_empty_string(
        review_artifact.get("artifact_kind"),
        "review_artifact.artifact_kind",
    ):
        raise ValueError("adjudication source_artifact_kind does not match review artifact")
    source_artifact_version = require_non_empty_string(
        adjudication_payload.get("source_artifact_version"),
        "source_artifact_version",
    )
    if source_artifact_version != require_non_empty_string(
        review_artifact.get("artifact_version"),
        "review_artifact.artifact_version",
    ):
        raise ValueError("adjudication source_artifact_version does not match review artifact")
    adjudication_source_export = require_object(
        adjudication_payload.get("source_export"),
        "source_export",
    )
    review_source_export = require_object(
        review_artifact.get("source_export"),
        "review_artifact.source_export",
    )
    for field_name in (
        "source_artifact",
        "source_project_id",
        "source_project_slug",
        "source_project_name",
    ):
        if adjudication_source_export.get(field_name) != review_source_export.get(field_name):
            raise ValueError(
                f"adjudication source_export.{field_name} does not match review artifact"
            )

    raw_decisions = require_object_list(adjudication_payload, "decisions")
    decisions_by_group: dict[str, dict[str, object]] = {}
    for index, decision in enumerate(raw_decisions):
        context = f"decisions[{index}]"
        group_id = require_non_empty_string(decision.get("group_id"), f"{context}.group_id")
        if group_id in decisions_by_group:
            raise ValueError(f"duplicate adjudication decision for group {group_id!r}")
        decisions_by_group[group_id] = {
            "selected_annotation_id": require_identifier(
                decision.get("selected_annotation_id"),
                f"{context}.selected_annotation_id",
            ),
            "adjudicator_id": normalize_optional_string(decision.get("adjudicator_id")),
            "decided_at": normalize_optional_string(decision.get("decided_at")),
            "decision_note": normalize_optional_string(decision.get("decision_note")),
        }
    return decisions_by_group


def _select_candidate_annotation(
    candidate_annotations: list[dict[str, object]],
    *,
    selected_annotation_id: str,
    context: str,
) -> dict[str, object]:
    for index, candidate in enumerate(candidate_annotations):
        candidate_context = f"{context}.candidate_annotations[{index}]"
        candidate_annotation_id = require_identifier(
            candidate.get("annotation_id"),
            f"{candidate_context}.annotation_id",
        )
        if candidate_annotation_id != selected_annotation_id:
            continue
        return {
            "annotation_id": candidate_annotation_id,
            "assignment_id": normalize_optional_string(candidate.get("assignment_id")),
            "assignment_backend": normalize_optional_string(candidate.get("assignment_backend")),
            "assignment_status": normalize_optional_string(candidate.get("assignment_status")),
            "submission_id": normalize_optional_string(candidate.get("submission_id")),
            "created_at": normalize_optional_string(candidate.get("created_at")),
            "schema_version": normalize_optional_string(candidate.get("schema_version")),
            "tool_version": normalize_optional_string(candidate.get("tool_version")),
            "objects": require_object_list(candidate, "objects"),
        }
    raise ValueError(
        "selected annotation id "
        f"{selected_annotation_id!r} is not present in {context}.candidate_annotations"
    )
