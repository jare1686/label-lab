"""Source adapter tests: COCO and anno-lab-raw loading, registry dispatch, and validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from label_lab.sources import (
    get_source_format_boundary,
    load_anno_lab_raw_source_dataset,
    load_coco_source_dataset,
    load_labelme_source_dataset,
)
from label_lab.sources.coco import load_coco_source_dataset as _load_coco
from label_lab.sources.registry import list_source_format_boundaries, load_source_dataset

FIXTURES_ROOT = Path(__file__).parent / "fixtures"
SOURCE_ANNO_LAB_RAW_FIXTURE = FIXTURES_ROOT / "demo_anno_lab_raw_export.json"
SOURCE_COCO_FIXTURE = FIXTURES_ROOT / "demo_source_coco.json"
SOURCE_LABELME_FIXTURE_DIR = FIXTURES_ROOT / "demo_source_labelme"
SOURCE_LABELME_SINGLE_FIXTURE = SOURCE_LABELME_FIXTURE_DIR / "scene_001.json"


def test_load_coco_source_dataset_reads_checked_in_fixture() -> None:
    dataset = load_coco_source_dataset(SOURCE_COCO_FIXTURE)

    assert dataset.source_format == "coco"
    assert dataset.source_path == SOURCE_COCO_FIXTURE.resolve()
    assert dataset.counts() == {
        "asset_count": 2,
        "annotation_count": 2,
        "category_count": 2,
    }
    assert dataset.images[0].split == "train"


def test_lvis_boundary_is_declared_with_explicit_extension_fields() -> None:
    boundary = get_source_format_boundary("lvis")

    assert boundary.adapter_family == "coco-family"
    assert boundary.release_ready is False
    assert boundary.asset_extension_fields == (
        "neg_category_ids",
        "not_exhaustive_category_ids",
    )
    assert boundary.category_extension_fields == ("frequency", "synonyms", "synset")


def test_load_anno_lab_raw_source_dataset_normalizes_checked_in_fixture() -> None:
    dataset = load_anno_lab_raw_source_dataset(SOURCE_ANNO_LAB_RAW_FIXTURE)

    assert dataset.source_format == "anno_lab_raw"
    assert dataset.source_path == SOURCE_ANNO_LAB_RAW_FIXTURE.resolve()
    assert dataset.counts() == {
        "asset_count": 2,
        "annotation_count": 3,
        "category_count": 2,
    }
    assert dataset.images[0].source_path_or_uri == "exports/train/slide_001.jpg"
    assert dataset.categories[0].name == "person"
    assert dataset.annotations[0]["bbox"] == [80.0, 60.0, 140.0, 220.0]
    assert dataset.adapter_metadata["source_contract"] == "anno_lab_raw_collection_export"
    assert dataset.adapter_metadata["normalization_profile"] == "anno_lab_instance_bbox_v1"


def test_load_labelme_source_dataset_normalizes_checked_in_directory_fixture() -> None:
    dataset = load_labelme_source_dataset(SOURCE_LABELME_FIXTURE_DIR)

    assert dataset.source_format == "labelme"
    assert dataset.source_path == SOURCE_LABELME_FIXTURE_DIR.resolve()
    assert dataset.counts() == {
        "asset_count": 2,
        "annotation_count": 2,
        "category_count": 2,
    }
    assert dataset.info["labelme_versions"] == ["5.5.0"]
    assert dataset.images[0].id == "scene_001"
    assert dataset.images[0].source_path_or_uri == "scene_001.jpg"
    assert dataset.annotations[0]["bbox"] == [120.0, 80.0, 140.0, 140.0]
    assert dataset.annotations[0]["labelme_group_id"] == "11"
    assert dataset.annotations[1]["segmentation"] == [[50.0, 60.0, 80.0, 40.0, 90.0, 90.0]]
    assert dataset.annotations[1]["labelme_flags"] == {"reviewed": True}


def test_load_labelme_source_dataset_accepts_single_json_file() -> None:
    dataset = load_labelme_source_dataset(SOURCE_LABELME_SINGLE_FIXTURE)

    assert dataset.source_path == SOURCE_LABELME_SINGLE_FIXTURE.resolve()
    assert dataset.counts() == {
        "asset_count": 1,
        "annotation_count": 1,
        "category_count": 1,
    }
    assert dataset.images[0].id == "scene_001"


def test_load_source_dataset_reads_anno_lab_raw_fixture() -> None:
    dataset = load_source_dataset(
        source_path=SOURCE_ANNO_LAB_RAW_FIXTURE,
        source_format="anno_lab_raw",
    )

    assert dataset.counts()["annotation_count"] == 3
    assert dataset.build_coco_payload()["info"]["source_project_slug"] == (
        "anno-lab-raw-demo"
    )


def test_load_source_dataset_reads_labelme_fixture_directory() -> None:
    dataset = load_source_dataset(
        source_path=SOURCE_LABELME_FIXTURE_DIR,
        source_format="labelme",
    )

    assert dataset.counts()["annotation_count"] == 2
    assert dataset.build_coco_payload()["info"]["source_format"] == "labelme"


def test_load_anno_lab_raw_rejects_multiple_annotations_per_task(tmp_path: Path) -> None:
    payload = _load_json(SOURCE_ANNO_LAB_RAW_FIXTURE)
    annotations = payload["annotations"]
    summary = payload["summary"]
    assert isinstance(annotations, list)
    assert isinstance(summary, dict)
    annotations.append(
        {
            "id": 703,
            "task_id": 501,
            "assignment_id": 602,
            "result": {"objects": []},
            "schema_version": "1.0.0",
            "tool_version": "instance-bbox@0.1.5",
        }
    )
    summary["annotation_count"] = 3
    source_path = _write_payload(tmp_path, payload)

    with pytest.raises(
        ValueError,
        match=(
            "multiple annotations for one task; run emit-review-groups "
            "before direct release emission"
        ),
    ):
        load_anno_lab_raw_source_dataset(source_path)


def test_load_anno_lab_raw_rejects_unsupported_result_shape(tmp_path: Path) -> None:
    payload = _load_json(SOURCE_ANNO_LAB_RAW_FIXTURE)
    annotations = payload["annotations"]
    assert isinstance(annotations, list)
    first_annotation = annotations[0]
    assert isinstance(first_annotation, dict)
    first_annotation["result"] = {"label": "person"}
    source_path = _write_payload(tmp_path, payload)

    with pytest.raises(ValueError, match="result.objects must be a list"):
        load_anno_lab_raw_source_dataset(source_path)


def test_load_anno_lab_raw_rejects_unknown_export_version(tmp_path: Path) -> None:
    payload = _load_json(SOURCE_ANNO_LAB_RAW_FIXTURE)
    payload["export_version"] = "9.9.9"
    source_path = _write_payload(tmp_path, payload)

    with pytest.raises(ValueError, match="unsupported anno-lab export_version"):
        load_anno_lab_raw_source_dataset(source_path)


def test_load_source_dataset_rejects_lvis_until_adapter_lands() -> None:
    with pytest.raises(NotImplementedError, match="LVIS adapter boundary is declared"):
        load_source_dataset(source_path=SOURCE_COCO_FIXTURE, source_format="lvis")


def test_list_source_format_boundaries_reports_labelme_between_coco_and_lvis() -> None:
    boundaries = list_source_format_boundaries()

    assert [boundary.source_format for boundary in boundaries] == [
        "anno_lab_raw",
        "coco",
        "labelme",
        "lvis",
    ]


def test_labelme_boundary_declares_release_ready_extension_fields() -> None:
    boundary = get_source_format_boundary("labelme")

    assert boundary.adapter_family == "labelme"
    assert boundary.release_ready is True
    assert boundary.annotation_extension_fields == (
        "labelme_shape_type",
        "labelme_group_id",
        "labelme_flags",
    )


def test_load_source_dataset_rejects_unknown_format() -> None:
    with pytest.raises(ValueError, match="unsupported source_format"):
        load_source_dataset(source_path=SOURCE_COCO_FIXTURE, source_format="dicom")


def test_get_source_format_boundary_rejects_unknown_format() -> None:
    with pytest.raises(ValueError, match="unsupported source_format"):
        get_source_format_boundary("openLABEL")


def test_load_coco_rejects_non_json_file(tmp_path: Path) -> None:
    bad_file = tmp_path / "not_json.json"
    bad_file.write_text("not valid json {{{", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        load_coco_source_dataset(bad_file)


def test_load_coco_rejects_json_array_root(tmp_path: Path) -> None:
    bad_file = tmp_path / "array.json"
    bad_file.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(ValueError, match="expected JSON object"):
        load_coco_source_dataset(bad_file)


def test_load_coco_rejects_missing_images_field(tmp_path: Path) -> None:
    source_path = _write_payload(
        tmp_path,
        {"categories": [], "annotations": []},
    )

    with pytest.raises(ValueError, match="expected list field 'images'"):
        _load_coco(source_path)


def test_load_coco_rejects_duplicate_annotation_ids(tmp_path: Path) -> None:
    source_path = _write_payload(
        tmp_path,
        {
            "info": {"description": "dup"},
            "images": [{"id": 1, "file_name": "a.jpg", "width": 10, "height": 10}],
            "categories": [{"id": 1, "name": "obj"}],
            "annotations": [
                {"id": 100, "image_id": 1, "category_id": 1, "bbox": [0, 0, 5, 5]},
                {"id": 100, "image_id": 1, "category_id": 1, "bbox": [1, 1, 5, 5]},
            ],
        },
    )

    with pytest.raises(ValueError, match="duplicate annotation id"):
        _load_coco(source_path)


def test_load_anno_lab_raw_rejects_wrong_export_contract(tmp_path: Path) -> None:
    payload = _load_json(SOURCE_ANNO_LAB_RAW_FIXTURE)
    payload["export_contract"] = "some_other_contract"
    source_path = _write_payload(tmp_path, payload)

    with pytest.raises(ValueError, match="unsupported anno-lab export_contract"):
        load_anno_lab_raw_source_dataset(source_path)


def test_load_labelme_rejects_unsupported_shape_type(tmp_path: Path) -> None:
    payload = _load_json(SOURCE_LABELME_SINGLE_FIXTURE)
    shapes = payload["shapes"]
    assert isinstance(shapes, list)
    first_shape = shapes[0]
    assert isinstance(first_shape, dict)
    first_shape["shape_type"] = "point"
    source_path = _write_payload(tmp_path, payload)

    with pytest.raises(ValueError, match="unsupported; supported types: polygon, rectangle"):
        load_labelme_source_dataset(source_path)


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    source_path = tmp_path / "source.json"
    source_path.write_text(json.dumps(payload), encoding="utf-8")
    return source_path
