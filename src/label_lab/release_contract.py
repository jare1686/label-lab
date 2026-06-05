"""Producer-authority constants and immutable data types for the published release bundle.

This module is the public contract surface for emitted ``release_manifest.json``
field names, artifact names, and version identifiers.  Downstream consumers
should depend on these declarations rather than on label-lab internals.
"""

from __future__ import annotations

from dataclasses import dataclass

CONTRACT_NAME = "published_artifact_bundle_contract"
CONTRACT_VERSION = "1.0.0"
BUNDLE_KIND = "dataset_release_bundle"
PUBLISHER_REPO = "label-lab"
CANONICAL_ANNOTATION_FORMAT = "COCO"
RELEASE_MANIFEST_NAME = "release_manifest.json"
ANNOTATIONS_COCO_NAME = "annotations.coco.json"
ASSETS_TABLE_NAME = "assets.parquet"
CATEGORIES_TABLE_NAME = "categories.parquet"
REQUIRED_COUNT_KEYS = ("asset_count", "annotation_count", "category_count")


def _require_non_empty_string(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class ReleaseArtifactPaths:
    """Relative file names for the artifacts inside a published release bundle."""

    annotations_coco: str = ANNOTATIONS_COCO_NAME
    assets_table: str = ASSETS_TABLE_NAME
    categories_table: str = CATEGORIES_TABLE_NAME

    def __post_init__(self) -> None:
        for field_name, value in self.to_dict().items():
            _require_non_empty_string(value, f"artifact_paths.{field_name}")

    def to_dict(self) -> dict[str, str]:
        return {
            "annotations_coco": self.annotations_coco,
            "assets_table": self.assets_table,
            "categories_table": self.categories_table,
        }


@dataclass(frozen=True, slots=True)
class ReleaseDatasetIdentity:
    """Identifying metadata for the dataset described by a release bundle."""

    dataset_id: str
    dataset_name: str
    dataset_version: str

    def __post_init__(self) -> None:
        _require_non_empty_string(self.dataset_id, "dataset.dataset_id")
        _require_non_empty_string(self.dataset_name, "dataset.dataset_name")
        _require_non_empty_string(self.dataset_version, "dataset.dataset_version")

    def to_dict(self) -> dict[str, str]:
        return {
            "dataset_id": self.dataset_id,
            "dataset_name": self.dataset_name,
            "dataset_version": self.dataset_version,
        }


@dataclass(frozen=True, slots=True)
class ReleaseLineageEntry:
    """Single stage in the provenance chain recorded inside a release manifest."""

    stage: str
    repo: str
    commit_sha: str
    artifact: str
    notes: str

    def __post_init__(self) -> None:
        _require_non_empty_string(self.stage, "lineage.stage")
        _require_non_empty_string(self.repo, "lineage.repo")
        _require_non_empty_string(self.commit_sha, "lineage.commit_sha")
        _require_non_empty_string(self.artifact, "lineage.artifact")
        _require_non_empty_string(self.notes, "lineage.notes")

    def to_dict(self) -> dict[str, str]:
        return {
            "stage": self.stage,
            "repo": self.repo,
            "commit_sha": self.commit_sha,
            "artifact": self.artifact,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class ReleaseManifest:
    """Top-level manifest for a published release bundle.

    Construction validates all required fields, checks that ``task_types``
    contains no duplicates, and verifies that ``split_summary`` totals match
    ``counts["asset_count"]``.
    """

    release_id: str
    release_version: str
    publisher_commit_sha: str
    created_at_utc: str
    task_types: tuple[str, ...]
    artifact_paths: ReleaseArtifactPaths
    lineage: tuple[ReleaseLineageEntry, ...]
    split_summary: dict[str, int]
    dataset: ReleaseDatasetIdentity
    counts: dict[str, int]
    source_formats: tuple[str, ...] = (CANONICAL_ANNOTATION_FORMAT,)
    notes: tuple[str, ...] = ()
    contract_name: str = CONTRACT_NAME
    contract_version: str = CONTRACT_VERSION
    bundle_kind: str = BUNDLE_KIND
    publisher_repo: str = PUBLISHER_REPO
    canonical_annotation_format: str = CANONICAL_ANNOTATION_FORMAT

    def __post_init__(self) -> None:
        for string_field_name, string_value in (
            ("release_id", self.release_id),
            ("release_version", self.release_version),
            ("publisher_commit_sha", self.publisher_commit_sha),
            ("created_at_utc", self.created_at_utc),
            ("contract_name", self.contract_name),
            ("contract_version", self.contract_version),
            ("bundle_kind", self.bundle_kind),
            ("publisher_repo", self.publisher_repo),
            ("canonical_annotation_format", self.canonical_annotation_format),
        ):
            _require_non_empty_string(string_value, string_field_name)

        if len(self.task_types) != len(set(self.task_types)):
            raise ValueError("task_types must not contain duplicates")
        for task_type in self.task_types:
            _require_non_empty_string(task_type, "task_types[]")

        if not self.lineage:
            raise ValueError("lineage must contain at least one entry")

        if set(self.counts) != set(REQUIRED_COUNT_KEYS):
            raise ValueError(
                "counts must contain asset_count, annotation_count, and category_count"
            )
        for count_field_name, count_value in self.counts.items():
            if count_value < 0:
                raise ValueError(f"counts.{count_field_name} must be non-negative")

        split_total = 0
        for split_name, split_count in self.split_summary.items():
            _require_non_empty_string(split_name, "split_summary key")
            if split_count < 0:
                raise ValueError(f"split_summary.{split_name} must be non-negative")
            split_total += split_count
        if split_total != self.counts["asset_count"]:
            raise ValueError("split_summary must add up to asset_count")

    def to_dict(self) -> dict[str, object]:
        return {
            "contract_name": self.contract_name,
            "contract_version": self.contract_version,
            "bundle_kind": self.bundle_kind,
            "release_id": self.release_id,
            "release_version": self.release_version,
            "publisher_repo": self.publisher_repo,
            "publisher_commit_sha": self.publisher_commit_sha,
            "created_at_utc": self.created_at_utc,
            "canonical_annotation_format": self.canonical_annotation_format,
            "source_formats": list(self.source_formats),
            "task_types": list(self.task_types),
            "artifact_paths": self.artifact_paths.to_dict(),
            "lineage": [entry.to_dict() for entry in self.lineage],
            "split_summary": dict(self.split_summary),
            "dataset": self.dataset.to_dict(),
            "counts": dict(self.counts),
            "notes": list(self.notes),
        }
