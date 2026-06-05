"""Source format registry: boundary declarations and format-dispatched loading.

Each supported source format is registered with a :class:`SourceFormatBoundary`
that declares its adapter family, release-readiness, and extension fields.
:func:`load_source_dataset` dispatches to the correct adapter based on format.
"""

from __future__ import annotations

import logging
from pathlib import Path

from label_lab.sources.anno_lab_raw import load_anno_lab_raw_source_dataset
from label_lab.sources.coco import load_coco_source_dataset
from label_lab.sources.contracts import SourceDataset, SourceFormatBoundary
from label_lab.sources.labelme import load_labelme_source_dataset

logger = logging.getLogger(__name__)

ANNO_LAB_RAW_SOURCE_BOUNDARY = SourceFormatBoundary(
    source_format="anno_lab_raw",
    adapter_family="anno-lab-raw",
    release_ready=True,
    annotation_extension_fields=(
        "anno_lab_annotation_id",
        "anno_lab_task_id",
        "source_object_id",
    ),
    notes=(
        "anno-lab raw exports normalize through label-lab before any public COCO release.",
        (
            "The first release-ready path is intentionally bounded to single-annotation-per-task "
            "instance-bbox style exports."
        ),
    ),
)

COCO_SOURCE_BOUNDARY = SourceFormatBoundary(
    source_format="coco",
    adapter_family="coco-family",
    release_ready=True,
    notes=(
        "COCO is the current release-ready adapter and anchors the v1 published bundle.",
        "Source datasets that already publish COCO should enter through this boundary.",
    ),
)

LABELME_SOURCE_BOUNDARY = SourceFormatBoundary(
    source_format="labelme",
    adapter_family="labelme",
    release_ready=True,
    annotation_extension_fields=(
        "labelme_shape_type",
        "labelme_group_id",
        "labelme_flags",
    ),
    notes=(
        (
            "LabelMe JSON sidecars normalize through a standalone adapter that accepts "
            "single files or directories of per-image JSON files."
        ),
        (
            "This tranche is intentionally bounded to rectangle and polygon shapes; "
            "other LabelMe shape types stay fail-closed until a later adapter lands."
        ),
    ),
)

LVIS_SOURCE_BOUNDARY = SourceFormatBoundary(
    source_format="lvis",
    adapter_family="coco-family",
    release_ready=False,
    asset_extension_fields=("neg_category_ids", "not_exhaustive_category_ids"),
    category_extension_fields=("frequency", "synonyms", "synset"),
    notes=(
        "LVIS should normalize through the same COCO-family adapter seam as COCO.",
        (
            "LVIS-only metadata should stay in explicit sidecars or extended "
            "records until the contract widens deliberately."
        ),
    ),
)

SOURCE_FORMAT_BOUNDARIES = {
    ANNO_LAB_RAW_SOURCE_BOUNDARY.source_format: ANNO_LAB_RAW_SOURCE_BOUNDARY,
    COCO_SOURCE_BOUNDARY.source_format: COCO_SOURCE_BOUNDARY,
    LABELME_SOURCE_BOUNDARY.source_format: LABELME_SOURCE_BOUNDARY,
    LVIS_SOURCE_BOUNDARY.source_format: LVIS_SOURCE_BOUNDARY,
}


def list_source_format_boundaries() -> tuple[SourceFormatBoundary, ...]:
    """Return all declared boundaries sorted by format name."""
    return tuple(SOURCE_FORMAT_BOUNDARIES[key] for key in sorted(SOURCE_FORMAT_BOUNDARIES))


def get_source_format_boundary(source_format: str) -> SourceFormatBoundary:
    """Look up the boundary for *source_format* (case-insensitive).

    Raises:
        ValueError: If the format is not registered.
    """
    normalized_source_format = source_format.strip().lower()
    boundary = SOURCE_FORMAT_BOUNDARIES.get(normalized_source_format)
    if boundary is None:
        supported_formats = ", ".join(sorted(SOURCE_FORMAT_BOUNDARIES))
        raise ValueError(
            f"unsupported source_format {source_format!r}; expected one of {supported_formats}"
        )
    return boundary


def load_source_dataset(
    *,
    source_path: str | Path,
    source_format: str,
) -> SourceDataset:
    """Load and validate a source file, dispatching to the appropriate adapter.

    Raises:
        NotImplementedError: If the format is declared but has no adapter yet.
        ValueError: If the format is unknown or the source file is invalid.
    """
    boundary = get_source_format_boundary(source_format)
    logger.debug(
        "Dispatching to %s adapter for %s", boundary.adapter_family, boundary.source_format
    )
    if boundary.source_format == "anno_lab_raw":
        return load_anno_lab_raw_source_dataset(source_path)
    if boundary.source_format == "coco":
        return load_coco_source_dataset(source_path)
    if boundary.source_format == "labelme":
        return load_labelme_source_dataset(source_path)
    if boundary.source_format == "lvis":
        raise NotImplementedError(
            "LVIS adapter boundary is declared but the release-ready adapter is not implemented yet"
        )
    # get_source_format_boundary rejects unknown formats; this guards
    # against a new format being registered without a dispatch branch.
    raise NotImplementedError(f"no adapter for registered format {boundary.source_format!r}")
