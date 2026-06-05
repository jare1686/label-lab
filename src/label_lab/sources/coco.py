"""COCO-format source adapter: load, validate, and normalize COCO annotation files.

Validation covers referential integrity (image, category, and annotation IDs),
geometry constraints (bbox, polygon, RLE, and keypoint formats), and structural
requirements (no duplicate IDs, no dangling references).  All identifiers are
coerced to strings so downstream code can treat IDs uniformly.
"""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path

from label_lab.models import CanonicalCategory, CanonicalImage
from label_lab.sources.contracts import SourceDataset
from label_lab.sources.validation import (
    coerce_object,
    load_json_object,
    normalize_optional_string,
    require_identifier,
    require_non_empty_string,
    require_non_negative_int,
    require_numeric_list,
    require_object_list,
    require_positive_int,
)

logger = logging.getLogger(__name__)


def load_coco_source_dataset(source_path: str | Path) -> SourceDataset:
    """Load and validate a COCO-format JSON file into a :class:`SourceDataset`.

    Raises:
        ValueError: If the file is not valid JSON, is missing required fields,
            contains duplicate IDs, or has dangling references.
    """
    resolved_source_path = Path(source_path).resolve()
    payload = load_json_object(resolved_source_path)
    raw_images = require_object_list(payload, "images")
    raw_categories = require_object_list(payload, "categories")
    raw_annotations = require_object_list(payload, "annotations")
    info = coerce_object(payload.get("info"))

    image_ids, images = _build_canonical_images(raw_images)
    category_ids, categories = _build_canonical_categories(raw_categories)
    annotations = _normalize_annotations(
        raw_annotations,
        image_ids=image_ids,
        category_ids=category_ids,
    )

    logger.info(
        "Loaded COCO source: %d images, %d categories, %d annotations",
        len(images),
        len(categories),
        len(annotations),
    )

    return SourceDataset(
        source_format="coco",
        source_path=resolved_source_path,
        info=info,
        images=images,
        categories=categories,
        annotations=annotations,
    )


def build_split_summary(images: tuple[CanonicalImage, ...]) -> dict[str, int]:
    """Count images per split.  Missing or blank splits are bucketed as ``"unspecified"``."""
    counts: Counter[str] = Counter()
    for image in images:
        if image.split:
            counts[image.split] += 1
        else:
            counts["unspecified"] += 1
    return dict(sorted(counts.items()))


def infer_task_types(annotations: tuple[dict[str, object], ...]) -> tuple[str, ...]:
    """Infer task types from annotation geometry fields.

    Returns a sorted tuple.  Falls back to ``("classification",)`` when
    annotations exist but carry no spatial geometry.
    """
    task_types: set[str] = set()
    for annotation in annotations:
        if _has_value(annotation.get("bbox")):
            task_types.add("bbox")
        if _has_value(annotation.get("segmentation")):
            task_types.add("instance_segmentation")
        if _has_value(annotation.get("keypoints")):
            task_types.add("keypoints")
    if not task_types and annotations:
        task_types.add("classification")
    return tuple(sorted(task_types))


def read_dataset_name(info: dict[str, object], source_path: Path) -> str:
    """Extract the dataset name from COCO ``info``, falling back to the file stem."""
    for key in ("description", "dataset_name", "name"):
        value = info.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return source_path.stem


# ---------------------------------------------------------------------------
# Internal: typed model construction
# ---------------------------------------------------------------------------


def _build_canonical_images(
    raw_images: list[dict[str, object]],
) -> tuple[set[str], tuple[CanonicalImage, ...]]:
    image_ids: set[str] = set()
    images: list[CanonicalImage] = []
    for index, raw in enumerate(raw_images):
        context = f"images[{index}]"
        image_id = require_identifier(raw.get("id"), f"{context}.id")
        if image_id in image_ids:
            raise ValueError(f"duplicate image id {image_id!r}")
        image_ids.add(image_id)
        file_name = require_non_empty_string(raw.get("file_name"), f"{context}.file_name")
        width = require_positive_int(raw.get("width"), f"{context}.width")
        height = require_positive_int(raw.get("height"), f"{context}.height")
        split = raw.get("split")
        if split is not None and (not isinstance(split, str) or not split.strip()):
            raise ValueError(f"{context}.split must be a non-empty string when present")
        resolved_split = split.strip() if isinstance(split, str) and split.strip() else None
        source_path_or_uri = (
            normalize_optional_string(raw.get("source_path_or_uri"))
            or normalize_optional_string(raw.get("coco_url"))
            or file_name
        )
        images.append(
            CanonicalImage(
                id=image_id,
                file_name=file_name,
                width=width,
                height=height,
                source_path_or_uri=source_path_or_uri,
                split=resolved_split,
            )
        )
    return image_ids, tuple(images)


def _build_canonical_categories(
    raw_categories: list[dict[str, object]],
) -> tuple[set[str], tuple[CanonicalCategory, ...]]:
    category_ids: set[str] = set()
    categories: list[CanonicalCategory] = []
    for index, raw in enumerate(raw_categories):
        context = f"categories[{index}]"
        category_id = require_identifier(raw.get("id"), f"{context}.id")
        if category_id in category_ids:
            raise ValueError(f"duplicate category id {category_id!r}")
        category_ids.add(category_id)
        name = require_non_empty_string(raw.get("name"), f"{context}.name")
        supercategory = normalize_optional_string(raw.get("supercategory"))
        categories.append(
            CanonicalCategory(
                id=category_id,
                name=name,
                supercategory=supercategory,
            )
        )
    return category_ids, tuple(categories)


def _normalize_annotations(
    raw_annotations: list[dict[str, object]],
    *,
    image_ids: set[str],
    category_ids: set[str],
) -> tuple[dict[str, object], ...]:
    annotation_ids: set[str] = set()
    normalized: list[dict[str, object]] = []
    for index, annotation in enumerate(raw_annotations):
        context = f"annotations[{index}]"
        annotation_id = require_identifier(annotation.get("id"), f"{context}.id")
        if annotation_id in annotation_ids:
            raise ValueError(f"duplicate annotation id {annotation_id!r}")
        annotation_ids.add(annotation_id)

        image_id = require_identifier(annotation.get("image_id"), f"{context}.image_id")
        if image_id not in image_ids:
            raise ValueError(f"{context}.image_id references unknown image id {image_id!r}")

        category_id = require_identifier(annotation.get("category_id"), f"{context}.category_id")
        if category_id not in category_ids:
            raise ValueError(
                f"{context}.category_id references unknown category id {category_id!r}"
            )

        _validate_annotation_geometry(annotation, context)

        entry = {**annotation}
        entry["id"] = annotation_id
        entry["image_id"] = image_id
        entry["category_id"] = category_id
        normalized.append(entry)

    return tuple(normalized)


# ---------------------------------------------------------------------------
# Internal: geometry validation
# ---------------------------------------------------------------------------


def _validate_annotation_geometry(annotation: dict[str, object], context: str) -> None:
    bbox = annotation.get("bbox")
    if bbox is not None:
        values = require_numeric_list(bbox, f"{context}.bbox", expected_length=4)
        if values[2] < 0 or values[3] < 0:
            raise ValueError(f"{context}.bbox width and height must be non-negative")

    segmentation = annotation.get("segmentation")
    if segmentation is not None:
        _validate_segmentation(segmentation, f"{context}.segmentation")

    keypoints = annotation.get("keypoints")
    if keypoints is not None:
        values = require_numeric_list(keypoints, f"{context}.keypoints")
        if len(values) % 3 != 0:
            raise ValueError(f"{context}.keypoints must contain x,y,visibility triplets")

    area = annotation.get("area")
    if area is not None:
        if not isinstance(area, (int, float)) or isinstance(area, bool):
            raise ValueError(f"{context}.area must be numeric when present")
        if float(area) < 0:
            raise ValueError(f"{context}.area must be non-negative when present")


def _validate_segmentation(value: object, field_name: str) -> None:
    """Validate a COCO segmentation as either a polygon list or an RLE object.

    Polygons must be non-empty lists of even-length coordinate arrays (>= 6
    values each).  RLE objects must have a ``size`` of ``[height, width]``
    and ``counts`` as a non-empty run-length string or integer list.
    """
    if isinstance(value, list):
        if not value:
            raise ValueError(f"{field_name} must not be an empty list")
        for index, polygon in enumerate(value):
            numbers = require_numeric_list(polygon, f"{field_name}[{index}]")
            if len(numbers) < 6 or len(numbers) % 2 != 0:
                raise ValueError(
                    f"{field_name}[{index}] must contain an even number of coordinates"
                )
        return

    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a polygon list or RLE object")

    size = value.get("size")
    if not isinstance(size, list) or len(size) != 2:
        raise ValueError(f"{field_name}.size must contain [height, width]")
    for index, item in enumerate(size):
        require_positive_int(item, f"{field_name}.size[{index}]")

    counts = value.get("counts")
    if isinstance(counts, str) and counts.strip():
        return
    if isinstance(counts, list) and counts:
        for index, item in enumerate(counts):
            require_non_negative_int(item, f"{field_name}.counts[{index}]")
        return
    raise ValueError(f"{field_name}.counts must be a non-empty string or integer list")


def _has_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, dict, str, tuple, set)):
        return bool(value)
    return True
