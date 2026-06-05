"""Release bundle emission tests: fixture regression, contract shape, and error paths."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest

from label_lab.release import emit_release_bundle, emit_release_bundle_from_source

FIXTURES_ROOT = Path(__file__).parent / "fixtures"
SOURCE_ANNO_LAB_RAW_FIXTURE = FIXTURES_ROOT / "demo_anno_lab_raw_export.json"
SOURCE_COCO_FIXTURE = FIXTURES_ROOT / "demo_source_coco.json"
SOURCE_LABELME_FIXTURE = FIXTURES_ROOT / "demo_source_labelme"
RELEASE_BUNDLE_FIXTURE = FIXTURES_ROOT / "published_release_bundle_v1"


def test_emit_release_matches_checked_in_bundle_fixture(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "release"

    emit_release_bundle(
        source_coco_path=SOURCE_COCO_FIXTURE,
        output_dir=bundle_dir,
        release_version="1.2.0",
    )

    manifest = _load_json(bundle_dir / "release_manifest.json")
    fixture_manifest = _load_json(RELEASE_BUNDLE_FIXTURE / "release_manifest.json")

    assert _normalize_manifest(manifest) == _normalize_manifest(fixture_manifest)
    assert _load_json(bundle_dir / "annotations.coco.json") == _load_json(
        RELEASE_BUNDLE_FIXTURE / "annotations.coco.json"
    )
    assert pq.read_table(bundle_dir / "assets.parquet").to_pylist() == pq.read_table(
        RELEASE_BUNDLE_FIXTURE / "assets.parquet"
    ).to_pylist()
    assert pq.read_table(bundle_dir / "categories.parquet").to_pylist() == pq.read_table(
        RELEASE_BUNDLE_FIXTURE / "categories.parquet"
    ).to_pylist()


def test_checked_in_bundle_fixture_has_expected_contract_shape() -> None:
    manifest = _load_json(RELEASE_BUNDLE_FIXTURE / "release_manifest.json")
    assets = pq.read_table(RELEASE_BUNDLE_FIXTURE / "assets.parquet").to_pylist()
    categories = pq.read_table(RELEASE_BUNDLE_FIXTURE / "categories.parquet").to_pylist()

    assert manifest["contract_name"] == "published_artifact_bundle_contract"
    assert manifest["bundle_kind"] == "dataset_release_bundle"
    assert manifest["artifact_paths"] == {
        "annotations_coco": "annotations.coco.json",
        "assets_table": "assets.parquet",
        "categories_table": "categories.parquet",
    }
    assert manifest["split_summary"] == {"train": 1, "val": 1}
    assert len(assets) == 2
    assert assets[0]["source_path_or_uri"] == "https://example.com/images/scene_001.jpg"
    assert len(categories) == 2
    assert categories[1]["name"] == "reference-marker"


def test_emit_release_rejects_unknown_annotation_category(tmp_path: Path) -> None:
    source_path = _write_payload(
        tmp_path,
        {
            "info": {"description": "Invalid Category Fixture"},
            "images": [{"id": 1, "file_name": "scene_001.jpg", "width": 640, "height": 480}],
            "categories": [{"id": 10, "name": "signal-object"}],
            "annotations": [{"id": 100, "image_id": 1, "category_id": 999, "bbox": [1, 2, 3, 4]}],
        },
    )

    with pytest.raises(ValueError, match="unknown category id"):
        emit_release_bundle(
            source_coco_path=source_path,
            output_dir=tmp_path / "release",
            release_version="0.1.0",
        )


def test_emit_release_rejects_duplicate_asset_ids(tmp_path: Path) -> None:
    source_path = _write_payload(
        tmp_path,
        {
            "info": {"description": "Duplicate Asset Fixture"},
            "images": [
                {"id": 1, "file_name": "scene_001.jpg", "width": 640, "height": 480},
                {"id": 1, "file_name": "scene_002.jpg", "width": 800, "height": 600},
            ],
            "categories": [{"id": 10, "name": "signal-object"}],
            "annotations": [{"id": 100, "image_id": 1, "category_id": 10, "bbox": [1, 2, 3, 4]}],
        },
    )

    with pytest.raises(ValueError, match="duplicate image id"):
        emit_release_bundle(
            source_coco_path=source_path,
            output_dir=tmp_path / "release",
            release_version="0.1.0",
        )


def test_emit_release_bundle_from_anno_lab_raw_emits_bounded_coco_bundle(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "anno-lab-raw-release"

    summary = emit_release_bundle_from_source(
        source_path=SOURCE_ANNO_LAB_RAW_FIXTURE,
        source_format="anno_lab_raw",
        output_dir=bundle_dir,
        release_version="0.4.0",
    )

    manifest = _load_json(bundle_dir / "release_manifest.json")
    annotations = _load_json(bundle_dir / "annotations.coco.json")
    assets = pq.read_table(bundle_dir / "assets.parquet").to_pylist()
    categories = pq.read_table(bundle_dir / "categories.parquet").to_pylist()

    assert summary["release_id"] == "anno-lab-raw-demo-0-4-0"
    assert manifest["source_formats"] == ["ANNO_LAB_RAW"]
    assert manifest["task_types"] == ["bbox"]
    assert manifest["counts"] == {
        "asset_count": 2,
        "annotation_count": 3,
        "category_count": 2,
    }
    assert manifest["notes"] == [
        "Normalized from anno_lab_raw_collection_export v1.0.0.",
        "Adapter normalization profile: anno_lab_instance_bbox_v1.",
    ]
    assert annotations["info"]["source_project_slug"] == "anno-lab-raw-demo"
    assert len(annotations["annotations"]) == 3
    assert "WorkerId" not in json.dumps(annotations)
    assert assets[0]["source_path_or_uri"] == "exports/train/slide_001.jpg"
    assert assets[1]["split"] == "val"
    assert categories[0]["name"] == "person"
    assert categories[0]["supercategory"] == "instance_bbox"


def test_emit_release_bundle_from_labelme_emits_bounded_coco_bundle(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "labelme-release"

    summary = emit_release_bundle_from_source(
        source_path=SOURCE_LABELME_FIXTURE,
        source_format="labelme",
        output_dir=bundle_dir,
        release_version="0.5.0",
    )

    manifest = _load_json(bundle_dir / "release_manifest.json")
    annotations = _load_json(bundle_dir / "annotations.coco.json")
    assets = pq.read_table(bundle_dir / "assets.parquet").to_pylist()
    categories = pq.read_table(bundle_dir / "categories.parquet").to_pylist()

    assert summary["release_id"] == "demo-source-labelme-0-5-0"
    assert manifest["source_formats"] == ["LABELME"]
    assert manifest["task_types"] == ["bbox", "instance_segmentation"]
    assert manifest["counts"] == {
        "asset_count": 2,
        "annotation_count": 2,
        "category_count": 2,
    }
    assert annotations["info"]["source_format"] == "labelme"
    assert annotations["annotations"][0]["labelme_shape_type"] == "rectangle"
    assert annotations["annotations"][1]["segmentation"] == [[50.0, 60.0, 80.0, 40.0, 90.0, 90.0]]
    assert assets[0]["source_path_or_uri"] == "scene_001.jpg"
    assert categories[0]["name"] == "reference-marker"
    assert categories[1]["name"] == "signal-object"


def test_emit_release_bundle_from_source_rejects_lvis_until_adapter_lands(tmp_path: Path) -> None:
    with pytest.raises(NotImplementedError, match="lvis source support is shaped"):
        emit_release_bundle_from_source(
            source_path=SOURCE_COCO_FIXTURE,
            source_format="lvis",
            output_dir=tmp_path / "release",
            release_version="0.1.0",
        )


def test_emit_release_respects_custom_dataset_name(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "release"

    summary = emit_release_bundle(
        source_coco_path=SOURCE_COCO_FIXTURE,
        output_dir=bundle_dir,
        release_version="1.0.0",
        dataset_name="custom-dataset-name",
    )

    assert summary["release_id"] == "custom-dataset-name-1-0-0"
    manifest = _load_json(bundle_dir / "release_manifest.json")
    assert manifest["dataset"]["dataset_name"] == "custom-dataset-name"


def test_emit_release_rejects_unsupported_source_format(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported source_format"):
        emit_release_bundle_from_source(
            source_path=SOURCE_COCO_FIXTURE,
            source_format="dicom",
            output_dir=tmp_path / "release",
            release_version="0.1.0",
        )


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_manifest(manifest: dict[str, object]) -> dict[str, object]:
    normalized = copy.deepcopy(manifest)
    normalized.pop("publisher_commit_sha", None)
    normalized.pop("created_at_utc", None)
    lineage = normalized.get("lineage")
    if isinstance(lineage, list):
        for entry in lineage:
            if isinstance(entry, dict):
                entry.pop("commit_sha", None)
    return normalized


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    source_path = tmp_path / "annotations.json"
    source_path.write_text(json.dumps(payload), encoding="utf-8")
    return source_path
