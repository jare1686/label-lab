"""CLI entrypoint tests: version output and runtime artifact subcommands."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from label_lab.main import main

FIXTURES_ROOT = Path(__file__).parent / "fixtures"
SOURCE_ANNO_LAB_RAW_FIXTURE = FIXTURES_ROOT / "demo_anno_lab_raw_export.json"
SOURCE_ANNO_LAB_RAW_REPEATED_FIXTURE = (
    FIXTURES_ROOT / "demo_anno_lab_raw_repeated_measure_export.json"
)
REVIEW_ADJUDICATION_FIXTURE = FIXTURES_ROOT / "demo_anno_lab_raw_review_adjudication.json"
SOURCE_COCO_FIXTURE = FIXTURES_ROOT / "demo_source_coco.json"
SOURCE_LABELME_FIXTURE = FIXTURES_ROOT / "demo_source_labelme"


def test_main_without_args_prints_help(capsys) -> None:
    exit_code = main([])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "usage:" in captured.out.lower()


def test_main_version_flag_prints_version(capsys) -> None:
    exit_code = main(["--version"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "label-lab 0.1.0" in captured.out


def test_python_module_entrypoint_runs_main() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "label_lab.main", "--version"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "label-lab 0.1.0" in result.stdout


def test_emit_release_writes_contract_bundle_from_checked_in_fixture(
    tmp_path: Path,
    capsys,
) -> None:
    bundle_dir = tmp_path / "release"

    exit_code = main(
        [
            "emit-release",
            "--source-coco",
            str(SOURCE_COCO_FIXTURE),
            "--output-dir",
            str(bundle_dir),
            "--release-version",
            "1.2.0",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    manifest = json.loads((bundle_dir / "release_manifest.json").read_text(encoding="utf-8"))

    assert payload["release_id"] == "shared-release-fixture-1-2-0"
    assert manifest["artifact_paths"]["annotations_coco"] == "annotations.coco.json"
    assert manifest["split_summary"] == {"train": 1, "val": 1}
    assert manifest["counts"] == {
        "asset_count": 2,
        "annotation_count": 2,
        "category_count": 2,
    }


def test_emit_release_with_custom_dataset_name(
    tmp_path: Path,
    capsys,
) -> None:
    bundle_dir = tmp_path / "release"

    exit_code = main(
        [
            "emit-release",
            "--source-coco",
            str(SOURCE_COCO_FIXTURE),
            "--output-dir",
            str(bundle_dir),
            "--release-version",
            "1.0.0",
            "--dataset-name",
            "my-custom-name",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["release_id"] == "my-custom-name-1-0-0"


def test_emit_release_writes_contract_bundle_from_anno_lab_raw_fixture(
    tmp_path: Path,
    capsys,
) -> None:
    bundle_dir = tmp_path / "anno-lab-raw-release"

    exit_code = main(
        [
            "emit-release",
            "--source-anno-lab-raw",
            str(SOURCE_ANNO_LAB_RAW_FIXTURE),
            "--output-dir",
            str(bundle_dir),
            "--release-version",
            "0.4.0",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    manifest = json.loads((bundle_dir / "release_manifest.json").read_text(encoding="utf-8"))

    assert payload["release_id"] == "anno-lab-raw-demo-0-4-0"
    assert manifest["source_formats"] == ["ANNO_LAB_RAW"]
    assert manifest["task_types"] == ["bbox"]
    assert manifest["counts"] == {
        "asset_count": 2,
        "annotation_count": 3,
        "category_count": 2,
    }


def test_emit_release_writes_contract_bundle_from_labelme_fixture(
    tmp_path: Path,
    capsys,
) -> None:
    bundle_dir = tmp_path / "labelme-release"

    exit_code = main(
        [
            "emit-release",
            "--source-labelme",
            str(SOURCE_LABELME_FIXTURE),
            "--output-dir",
            str(bundle_dir),
            "--release-version",
            "0.5.0",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    manifest = json.loads((bundle_dir / "release_manifest.json").read_text(encoding="utf-8"))

    assert payload["release_id"] == "demo-source-labelme-0-5-0"
    assert manifest["source_formats"] == ["LABELME"]
    assert manifest["task_types"] == ["bbox", "instance_segmentation"]
    assert manifest["counts"] == {
        "asset_count": 2,
        "annotation_count": 2,
        "category_count": 2,
    }


def test_emit_review_groups_writes_repeated_measure_artifact(
    tmp_path: Path,
    capsys,
) -> None:
    artifact_path = tmp_path / "review-groups.json"

    exit_code = main(
        [
            "emit-review-groups",
            "--source-anno-lab-raw",
            str(SOURCE_ANNO_LAB_RAW_REPEATED_FIXTURE),
            "--output-path",
            str(artifact_path),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert payload["artifact_kind"] == "anno_lab_raw_review_groups"
    assert payload["review_group_count"] == 1
    assert payload["review_annotation_count"] == 2
    assert payload["single_annotation_task_count"] == 1
    assert artifact["normalization_profile"] == "anno_lab_repeated_measure_review_v1"
    assert artifact["review_groups"][0]["task_id"] == "501"


def test_emit_canonical_records_writes_adjudicated_import_artifact(
    tmp_path: Path,
    capsys,
) -> None:
    review_groups_path = tmp_path / "review-groups.json"
    canonical_records_path = tmp_path / "canonical-records.json"

    review_exit_code = main(
        [
            "emit-review-groups",
            "--source-anno-lab-raw",
            str(SOURCE_ANNO_LAB_RAW_REPEATED_FIXTURE),
            "--output-path",
            str(review_groups_path),
        ]
    )
    capsys.readouterr()
    assert review_exit_code == 0

    exit_code = main(
        [
            "emit-canonical-records",
            "--review-groups",
            str(review_groups_path),
            "--adjudication",
            str(REVIEW_ADJUDICATION_FIXTURE),
            "--output-path",
            str(canonical_records_path),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    artifact = json.loads(canonical_records_path.read_text(encoding="utf-8"))

    assert payload["artifact_kind"] == "anno_lab_raw_canonical_record_import"
    assert payload["review_group_count"] == 1
    assert payload["canonical_record_count"] == 1
    assert payload["single_annotation_task_count"] == 1
    assert artifact["normalization_profile"] == (
        "anno_lab_repeated_measure_canonical_record_import_v1"
    )
    assert artifact["canonical_records"][0]["selected_annotation"]["annotation_id"] == "703"
