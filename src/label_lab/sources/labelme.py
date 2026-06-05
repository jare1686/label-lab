"""LabelMe JSON source adapter.

Normalizes LabelMe-style per-image JSON sidecars into COCO-compatible source
datasets for release emission. This tranche supports only ``rectangle`` and
``polygon`` shapes; other LabelMe shape types fail closed until a later
adapter tranche widens the boundary deliberately.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from label_lab.models import CanonicalCategory, CanonicalImage
from label_lab.sources.contracts import SourceDataset
from label_lab.sources.validation import (
    coerce_object,
    is_number,
    load_json_object,
    normalize_optional_string,
    require_identifier,
    require_non_empty_string,
    require_object,
    require_object_list,
    require_positive_int,
)

logger = logging.getLogger(__name__)

SUPPORTED_LABELME_SHAPE_TYPES = ("polygon", "rectangle")


@dataclass(frozen=True, slots=True)
class _LabelMeShapeContext:
    """Single normalized LabelMe shape bound to one image."""

    annotation_id: str
    label: str
    shape_type: str
    points: tuple[tuple[float, float], ...]
    group_id: str | None
    flags: dict[str, object]


@dataclass(frozen=True, slots=True)
class _LabelMeImageContext:
    """Validated LabelMe sidecar plus its shapes."""

    image_id: str
    json_path: Path
    image: CanonicalImage
    version: str | None
    shapes: tuple[_LabelMeShapeContext, ...]


def load_labelme_source_dataset(source_path: str | Path) -> SourceDataset:
    """Load LabelMe JSON sidecars into a normalized :class:`SourceDataset`.

    ``source_path`` may point to a single JSON file or to a directory
    containing per-image JSON sidecars.
    """
    resolved_source_path = Path(source_path).resolve()
    source_files = _discover_labelme_files(resolved_source_path)
    source_root = (
        resolved_source_path
        if resolved_source_path.is_dir()
        else resolved_source_path.parent
    )
    image_contexts = tuple(
        _load_labelme_image_context(
            source_file,
            source_root=source_root,
        )
        for source_file in source_files
    )

    images = _build_images(image_contexts)
    categories, category_ids_by_label = _build_categories(image_contexts)
    annotations = _build_annotations(
        image_contexts,
        category_ids_by_label=category_ids_by_label,
    )
    labelme_versions = sorted(
        {
            version
            for version in (context.version for context in image_contexts)
            if version is not None
        }
    )
    dataset_name = resolved_source_path.stem

    info: dict[str, object] = {
        "description": dataset_name,
        "source_format": "labelme",
    }
    if labelme_versions:
        info["labelme_versions"] = labelme_versions

    logger.info(
        "Loaded LabelMe source: %d images, %d categories, %d annotations",
        len(images),
        len(categories),
        len(annotations),
    )

    return SourceDataset(
        source_format="labelme",
        source_path=resolved_source_path,
        info=info,
        images=images,
        categories=categories,
        annotations=annotations,
        adapter_metadata={
            "input_mode": "directory" if resolved_source_path.is_dir() else "file",
            "source_file_count": len(image_contexts),
        },
    )


def _discover_labelme_files(source_path: Path) -> tuple[Path, ...]:
    if not source_path.exists():
        raise ValueError(f"LabelMe source path does not exist: {source_path}")

    if source_path.is_dir():
        sidecar_files = tuple(
            sorted(
                (
                    path
                    for path in source_path.iterdir()
                    if path.is_file() and path.suffix.lower() == ".json"
                ),
                key=lambda path: path.name,
            )
        )
        if not sidecar_files:
            raise ValueError(
                f"LabelMe source directory must contain at least one .json file: {source_path}"
            )
        return sidecar_files

    if source_path.suffix.lower() != ".json":
        raise ValueError(f"LabelMe source file must end with .json: {source_path}")
    return (source_path,)


def _load_labelme_image_context(
    source_file: Path,
    *,
    source_root: Path,
) -> _LabelMeImageContext:
    payload = load_json_object(source_file)
    source_context = str(source_file)
    image_id = _build_image_id(source_file, source_root=source_root)
    image_path = require_non_empty_string(payload.get("imagePath"), f"{source_context}.imagePath")
    width = require_positive_int(payload.get("imageWidth"), f"{source_context}.imageWidth")
    height = require_positive_int(payload.get("imageHeight"), f"{source_context}.imageHeight")
    raw_shapes = require_object_list(payload, "shapes")
    shapes = tuple(
        _build_shape_context(
            raw_shape,
            annotation_id=f"{image_id}:{shape_index}",
            field_name=f"{source_context}.shapes[{shape_index - 1}]",
        )
        for shape_index, raw_shape in enumerate(raw_shapes, start=1)
    )

    return _LabelMeImageContext(
        image_id=image_id,
        json_path=source_file,
        image=CanonicalImage(
            id=image_id,
            file_name=Path(image_path).name,
            width=width,
            height=height,
            source_path_or_uri=image_path,
        ),
        version=normalize_optional_string(payload.get("version")),
        shapes=shapes,
    )


def _build_image_id(source_file: Path, *, source_root: Path) -> str:
    relative_path = source_file.relative_to(source_root)
    if relative_path.suffix:
        relative_path = relative_path.with_suffix("")
    image_id = relative_path.as_posix()
    if not image_id:
        raise ValueError(f"Could not derive deterministic image id for {source_file}")
    return image_id


def _build_shape_context(
    raw_shape: dict[str, object],
    *,
    annotation_id: str,
    field_name: str,
) -> _LabelMeShapeContext:
    label = require_non_empty_string(raw_shape.get("label"), f"{field_name}.label")
    shape_type = require_non_empty_string(
        raw_shape.get("shape_type"),
        f"{field_name}.shape_type",
    ).lower()
    if shape_type not in SUPPORTED_LABELME_SHAPE_TYPES:
        supported_types = ", ".join(SUPPORTED_LABELME_SHAPE_TYPES)
        raise ValueError(
            f"{field_name}.shape_type {shape_type!r} is unsupported; "
            f"supported types: {supported_types}"
        )
    points = _require_points(raw_shape.get("points"), f"{field_name}.points")
    if shape_type == "rectangle" and len(points) != 2:
        raise ValueError(f"{field_name}.points must contain exactly 2 points for rectangle")
    if shape_type == "polygon" and len(points) < 3:
        raise ValueError(f"{field_name}.points must contain at least 3 points for polygon")

    group_id = raw_shape.get("group_id")
    normalized_group_id = (
        require_identifier(group_id, f"{field_name}.group_id") if group_id is not None else None
    )

    flags_value = raw_shape.get("flags")
    flags = require_object(flags_value, f"{field_name}.flags") if flags_value is not None else {}

    return _LabelMeShapeContext(
        annotation_id=annotation_id,
        label=label,
        shape_type=shape_type,
        points=points,
        group_id=normalized_group_id,
        flags=flags,
    )


def _require_points(value: object, field_name: str) -> tuple[tuple[float, float], ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field_name} must be a non-empty list")

    normalized_points: list[tuple[float, float]] = []
    for index, point in enumerate(value):
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError(f"{field_name}[{index}] must contain exactly two numeric coordinates")
        x, y = point
        if not is_number(x) or not is_number(y):
            raise ValueError(f"{field_name}[{index}] must contain exactly two numeric coordinates")
        normalized_points.append((float(x), float(y)))
    return tuple(normalized_points)


def _build_images(
    image_contexts: tuple[_LabelMeImageContext, ...],
) -> tuple[CanonicalImage, ...]:
    image_ids: set[str] = set()
    images: list[CanonicalImage] = []
    for context in image_contexts:
        if context.image_id in image_ids:
            raise ValueError(f"duplicate LabelMe image id {context.image_id!r}")
        image_ids.add(context.image_id)
        images.append(context.image)
    return tuple(images)


def _build_categories(
    image_contexts: tuple[_LabelMeImageContext, ...],
) -> tuple[tuple[CanonicalCategory, ...], dict[str, str]]:
    labels = sorted({shape.label for context in image_contexts for shape in context.shapes})
    categories: list[CanonicalCategory] = []
    category_ids_by_label: dict[str, str] = {}
    for index, label in enumerate(labels, start=1):
        category_id = str(index)
        category_ids_by_label[label] = category_id
        categories.append(CanonicalCategory(id=category_id, name=label))
    return tuple(categories), category_ids_by_label


def _build_annotations(
    image_contexts: tuple[_LabelMeImageContext, ...],
    *,
    category_ids_by_label: dict[str, str],
) -> tuple[dict[str, object], ...]:
    annotations: list[dict[str, object]] = []
    for context in image_contexts:
        for shape in context.shapes:
            annotation: dict[str, object] = {
                "id": shape.annotation_id,
                "image_id": context.image_id,
                "category_id": category_ids_by_label[shape.label],
                "bbox": _build_bbox(shape.points),
                "labelme_shape_type": shape.shape_type,
            }
            if shape.shape_type == "polygon":
                annotation["segmentation"] = [_flatten_points(shape.points)]
            if shape.group_id is not None:
                annotation["labelme_group_id"] = shape.group_id
            if shape.flags:
                annotation["labelme_flags"] = coerce_object(shape.flags)
            annotations.append(annotation)
    return tuple(annotations)


def _build_bbox(points: tuple[tuple[float, float], ...]) -> list[float]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x = min(xs)
    min_y = min(ys)
    max_x = max(xs)
    max_y = max(ys)
    return [min_x, min_y, max_x - min_x, max_y - min_y]


def _flatten_points(points: tuple[tuple[float, float], ...]) -> list[float]:
    flattened: list[float] = []
    for x, y in points:
        flattened.extend((x, y))
    return flattened
