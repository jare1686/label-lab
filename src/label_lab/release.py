"""Emit contract-compliant published release bundles from validated source datasets.

Bundles contain ``release_manifest.json``, ``annotations.coco.json``, and
Parquet sidecar tables for assets and categories.  All emitted field names and
artifact names are governed by :mod:`label_lab.release_contract`.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import warnings
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from label_lab.release_contract import (
    PUBLISHER_REPO,
    RELEASE_MANIFEST_NAME,
    ReleaseArtifactPaths,
    ReleaseDatasetIdentity,
    ReleaseLineageEntry,
    ReleaseManifest,
)
from label_lab.sources.coco import (
    build_split_summary,
    infer_task_types,
    read_dataset_name,
)
from label_lab.sources.contracts import SourceDataset
from label_lab.sources.registry import get_source_format_boundary, load_source_dataset
from label_lab.sources.validation import normalize_optional_string

logger = logging.getLogger(__name__)


def emit_release_bundle(
    *,
    source_coco_path: str | Path,
    output_dir: str | Path,
    release_version: str,
    dataset_name: str | None = None,
) -> dict[str, object]:
    """Emit a release bundle from a COCO-format source file.

    This is a convenience wrapper around :func:`emit_release_bundle_from_source`
    with ``source_format="coco"``.
    """
    return emit_release_bundle_from_source(
        source_path=source_coco_path,
        source_format="coco",
        output_dir=output_dir,
        release_version=release_version,
        dataset_name=dataset_name,
    )


def emit_release_bundle_from_source(
    *,
    source_path: str | Path,
    source_format: str,
    output_dir: str | Path,
    release_version: str,
    dataset_name: str | None = None,
) -> dict[str, object]:
    """Emit a release bundle from any supported source format.

    Raises:
        NotImplementedError: If the source format is declared but not yet
            release-ready (e.g. LVIS).
        ValueError: If the source file fails validation.
    """
    boundary = get_source_format_boundary(source_format)
    if not boundary.release_ready:
        raise NotImplementedError(
            f"{boundary.source_format} source support is shaped but not release-ready yet"
        )
    source_dataset = load_source_dataset(
        source_path=source_path,
        source_format=boundary.source_format,
    )
    return _emit_release_bundle_from_source_dataset(
        source_dataset=source_dataset,
        output_dir=output_dir,
        release_version=release_version,
        dataset_name=dataset_name,
    )


def _emit_release_bundle_from_source_dataset(
    *,
    source_dataset: SourceDataset,
    output_dir: str | Path,
    release_version: str,
    dataset_name: str | None = None,
) -> dict[str, object]:
    bundle_dir = Path(output_dir).resolve()
    resolved_dataset_name = dataset_name or read_dataset_name(
        source_dataset.info,
        source_dataset.source_path,
    )
    dataset_id = _slugify(resolved_dataset_name)
    release_id = f"{dataset_id}-{_slugify(release_version)}"
    task_types = infer_task_types(source_dataset.annotations)
    split_summary = build_split_summary(source_dataset.images)
    counts = source_dataset.counts()
    publisher_commit_sha = _git_head_sha()
    artifact_paths = ReleaseArtifactPaths()
    manifest_notes = _build_manifest_notes(source_dataset)

    logger.info("Emitting release bundle %s to %s", release_id, bundle_dir)

    bundle_dir.mkdir(parents=True, exist_ok=True)
    annotations_path = bundle_dir / artifact_paths.annotations_coco
    assets_table_path = bundle_dir / artifact_paths.assets_table
    categories_table_path = bundle_dir / artifact_paths.categories_table
    manifest_path = bundle_dir / RELEASE_MANIFEST_NAME

    annotations_path.write_text(
        json.dumps(source_dataset.build_coco_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_table(
        assets_table_path,
        [image.to_asset_row(dataset_id) for image in source_dataset.images],
    )
    _write_table(
        categories_table_path,
        [category.to_category_row(dataset_id) for category in source_dataset.categories],
    )

    manifest = ReleaseManifest(
        release_id=release_id,
        release_version=release_version,
        publisher_commit_sha=publisher_commit_sha,
        created_at_utc=_utc_now(),
        task_types=task_types,
        artifact_paths=artifact_paths,
        lineage=(
            ReleaseLineageEntry(
                stage="source_ingest",
                repo=PUBLISHER_REPO,
                commit_sha=publisher_commit_sha,
                artifact=_sanitize_source_reference(source_dataset.source_path),
                notes=(
                    f"Source {source_dataset.source_format.upper()} annotations "
                    "used as the release input."
                ),
            ),
            ReleaseLineageEntry(
                stage="publication",
                repo=PUBLISHER_REPO,
                commit_sha=publisher_commit_sha,
                artifact=manifest_path.name,
                notes="Portable contract bundle emitted by label-lab.",
            ),
        ),
        split_summary=split_summary,
        dataset=ReleaseDatasetIdentity(
            dataset_id=dataset_id,
            dataset_name=resolved_dataset_name,
            dataset_version=release_version,
        ),
        counts=counts,
        source_formats=(source_dataset.source_format.upper(),),
        notes=manifest_notes,
    )
    manifest_path.write_text(
        json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    logger.info("Release bundle %s complete", release_id)

    return {
        "bundle_dir": str(bundle_dir),
        "release_id": release_id,
        "release_version": release_version,
        "task_types": list(task_types),
        "counts": counts,
        "artifacts": {
            "manifest": str(manifest_path),
            "annotations_coco": str(annotations_path),
            "assets_table": str(assets_table_path),
            "categories_table": str(categories_table_path),
        },
    }


def _write_table(path: Path, rows: list[dict[str, object]]) -> None:
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path)


def _slugify(value: str) -> str:
    """Convert *value* to a lowercase alphanumeric slug, falling back to ``"release"``."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "release"


def _git_head_sha() -> str:
    """Return the current git HEAD SHA, or ``"unknown"`` if git is unavailable."""
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    head = result.stdout.strip()
    if result.returncode != 0 or not head:
        warnings.warn(
            "Could not determine git HEAD SHA; "
            "publisher_commit_sha will be recorded as 'unknown'",
            stacklevel=2,
        )
        return "unknown"
    return head


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sanitize_source_reference(source_path: Path) -> str:
    """Return only the file name to avoid recording local directory structure."""
    return source_path.name


def _build_manifest_notes(source_dataset: SourceDataset) -> tuple[str, ...]:
    """Build provenance notes from adapter metadata, if present."""
    notes: list[str] = []
    source_contract = normalize_optional_string(
        source_dataset.adapter_metadata.get("source_contract")
    )
    source_contract_version = normalize_optional_string(
        source_dataset.adapter_metadata.get("source_contract_version")
    )
    normalization_profile = normalize_optional_string(
        source_dataset.adapter_metadata.get("normalization_profile")
    )
    if source_contract is not None and source_contract_version is not None:
        notes.append(f"Normalized from {source_contract} v{source_contract_version}.")
    if normalization_profile is not None:
        notes.append(f"Adapter normalization profile: {normalization_profile}.")
    return tuple(notes)
