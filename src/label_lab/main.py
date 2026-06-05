"""CLI entrypoint for the label-lab framework.

Provides ``emit-release``, ``emit-review-groups``, and
``emit-canonical-records`` for bounded release emission and repeated-measure
adjudication artifacts.
"""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from label_lab import __version__
from label_lab.adjudication import (
    emit_anno_lab_raw_canonical_record_import_artifact,
    emit_anno_lab_raw_review_artifact,
)
from label_lab.release import emit_release_bundle, emit_release_bundle_from_source


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="label-lab",
        description="Dataset ingestion, cleaning, conversion, and analysis framework.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print the label-lab package version and exit.",
    )
    subparsers = parser.add_subparsers(dest="command")
    emit_release = subparsers.add_parser(
        "emit-release",
        help="Emit a contract-compliant published release bundle from a supported source export.",
    )
    source_group = emit_release.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--source-coco",
        help="Path to the source COCO annotations JSON file.",
    )
    source_group.add_argument(
        "--source-anno-lab-raw",
        help="Path to the source anno-lab raw collection export JSON file.",
    )
    source_group.add_argument(
        "--source-labelme",
        help=(
            "Path to a LabelMe JSON file or to a directory containing per-image "
            "LabelMe JSON sidecars."
        ),
    )
    emit_release.add_argument(
        "--output-dir",
        required=True,
        help="Directory where the release bundle should be written.",
    )
    emit_release.add_argument(
        "--release-version",
        required=True,
        help="Semantic version or bounded release label for the emitted bundle.",
    )
    emit_release.add_argument(
        "--dataset-name",
        help=(
            "Optional dataset name override. Defaults to the COCO payload "
            "info description or file stem."
        ),
    )
    emit_review_groups = subparsers.add_parser(
        "emit-review-groups",
        help=(
            "Emit a repo-local review artifact for repeated-measure anno-lab raw exports."
        ),
    )
    emit_review_groups.add_argument(
        "--source-anno-lab-raw",
        required=True,
        help="Path to the repeated-measure anno-lab raw collection export JSON file.",
    )
    emit_review_groups.add_argument(
        "--output-path",
        required=True,
        help="Path where the review-groups artifact JSON should be written.",
    )
    emit_canonical_records = subparsers.add_parser(
        "emit-canonical-records",
        help=(
            "Emit a repo-local canonical-record import artifact from review groups "
            "plus adjudication decisions."
        ),
    )
    emit_canonical_records.add_argument(
        "--review-groups",
        required=True,
        help="Path to the review-groups artifact JSON file.",
    )
    emit_canonical_records.add_argument(
        "--adjudication",
        required=True,
        help="Path to the adjudication decisions JSON file.",
    )
    emit_canonical_records.add_argument(
        "--output-path",
        required=True,
        help="Path where the canonical-record import artifact JSON should be written.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse *argv* and dispatch to the requested subcommand.

    Returns 0 on success.  When no subcommand is given, prints help.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(f"label-lab {__version__}")
        return 0

    if args.command == "emit-release":
        if args.source_coco:
            summary = emit_release_bundle(
                source_coco_path=args.source_coco,
                output_dir=args.output_dir,
                release_version=args.release_version,
                dataset_name=args.dataset_name,
            )
        elif args.source_anno_lab_raw:
            summary = emit_release_bundle_from_source(
                source_path=args.source_anno_lab_raw,
                source_format="anno_lab_raw",
                output_dir=args.output_dir,
                release_version=args.release_version,
                dataset_name=args.dataset_name,
            )
        else:
            summary = emit_release_bundle_from_source(
                source_path=args.source_labelme,
                source_format="labelme",
                output_dir=args.output_dir,
                release_version=args.release_version,
                dataset_name=args.dataset_name,
            )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    if args.command == "emit-review-groups":
        summary = emit_anno_lab_raw_review_artifact(
            source_path=args.source_anno_lab_raw,
            output_path=args.output_path,
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    if args.command == "emit-canonical-records":
        summary = emit_anno_lab_raw_canonical_record_import_artifact(
            review_groups_path=args.review_groups,
            adjudication_path=args.adjudication,
            output_path=args.output_path,
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
