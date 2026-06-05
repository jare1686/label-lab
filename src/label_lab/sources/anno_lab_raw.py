"""Anno-lab raw collection export adapter.

Normalizes private ``anno_lab_raw_collection_export@1.0.0`` bundles into
COCO-compatible structures for downstream release emission. The first
release-ready profile (``anno_lab_instance_bbox_v1``) is bounded to
single-annotation-per-task, instance-bbox-style exports. Repeated-measure
exports stay out of the direct release path and instead materialize as an
explicit repo-local review artifact until adjudication hardens.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from label_lab.models import CanonicalCategory, CanonicalImage
from label_lab.sources.contracts import SourceDataset
from label_lab.sources.validation import (
    coerce_int,
    coerce_object,
    load_json_object,
    normalize_optional_string,
    require_identifier,
    require_non_empty_string,
    require_object,
    require_object_list,
    require_positive_int,
)

logger = logging.getLogger(__name__)

ANNO_LAB_RAW_EXPORT_CONTRACT = "anno_lab_raw_collection_export"
ANNO_LAB_RAW_EXPORT_VERSION = "1.0.0"
ANNO_LAB_INSTANCE_BBOX_NORMALIZATION_PROFILE = "anno_lab_instance_bbox_v1"
ANNO_LAB_REPEATED_MEASURE_REVIEW_PROFILE = "anno_lab_repeated_measure_review_v1"
ANNO_LAB_REVIEW_GROUPS_ARTIFACT_KIND = "anno_lab_raw_review_groups"
ANNO_LAB_REVIEW_GROUPS_ARTIFACT_VERSION = "1.0.0"
SUPPORTED_ANNO_LAB_TASK_TYPES = ("bbox", "instance_bbox")


@dataclass(frozen=True, slots=True)
class _TaskDefinitionContext:
    """Intermediate context extracted from a raw task definition record."""

    task_definition_id: str
    task_type_slug: str
    object_classes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _TaskContext:
    """Intermediate context linking a task to its asset and definition."""

    task_id: str
    asset_id: str
    task_definition: _TaskDefinitionContext


@dataclass(frozen=True, slots=True)
class _AssignmentContext:
    """Operator-safe assignment metadata retained for review grouping only."""

    assignment_id: str
    task_id: str
    backend: str | None
    status: str | None
    created_at: str | None
    updated_at: str | None


@dataclass(frozen=True, slots=True)
class _AnnotationObjectContext:
    """Single normalized object candidate from a raw annotation record."""

    object_id: str
    label: str
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class _AnnotationContext:
    """Sanitized repeated-measure candidate or release-ready annotation record."""

    annotation_id: str
    task_id: str
    assignment_id: str | None
    schema_version: str | None
    tool_version: str | None
    submission_id: str | None
    created_at: str | None
    objects: tuple[_AnnotationObjectContext, ...]


@dataclass(frozen=True, slots=True)
class _AnnoLabRawExportContext:
    """Validated raw-export context shared by release and review paths."""

    source_path: Path
    project: dict[str, object]
    exported_at: str | None
    images: tuple[CanonicalImage, ...]
    tasks_by_id: dict[str, _TaskContext]
    assignments_by_id: dict[str, _AssignmentContext]
    annotations: tuple[_AnnotationContext, ...]
    raw_summary: dict[str, int]


def load_anno_lab_raw_source_dataset(source_path: str | Path) -> SourceDataset:
    """Load and normalize an anno-lab raw collection export into a :class:`SourceDataset`.

    Validates the export contract and version, enforces single-annotation-per-task,
    and maps anno-lab entities to COCO-compatible images, categories, and
    annotations.  Worker identifiers and raw assignment payloads are excluded
    from the output.

    Raises:
        ValueError: If the export contract, version, or content is invalid.
    """
    context = _load_anno_lab_raw_export_context(source_path)

    _validate_single_annotation_per_task(context.annotations)
    categories, category_ids_by_label = _build_categories(context.tasks_by_id)
    coco_annotations = _build_annotations(
        context.annotations,
        tasks_by_id=context.tasks_by_id,
        category_ids_by_label=category_ids_by_label,
    )

    info = _build_info(
        project=context.project,
        exported_at=context.exported_at,
    )

    logger.info(
        "Loaded anno-lab raw source (%s): %d images, %d categories, %d annotations",
        ANNO_LAB_INSTANCE_BBOX_NORMALIZATION_PROFILE,
        len(context.images),
        len(categories),
        len(coco_annotations),
    )

    return SourceDataset(
        source_format="anno_lab_raw",
        source_path=context.source_path,
        info=info,
        images=context.images,
        categories=categories,
        annotations=coco_annotations,
        adapter_metadata={
            "source_contract": ANNO_LAB_RAW_EXPORT_CONTRACT,
            "source_contract_version": ANNO_LAB_RAW_EXPORT_VERSION,
            "normalization_profile": ANNO_LAB_INSTANCE_BBOX_NORMALIZATION_PROFILE,
            "source_project_slug": require_non_empty_string(
                context.project.get("slug"),
                "project.slug",
            ),
            "source_project_name": require_non_empty_string(
                context.project.get("name"),
                "project.name",
            ),
            "raw_summary": dict(context.raw_summary),
        },
    )


def build_anno_lab_raw_review_artifact(source_path: str | Path) -> dict[str, object]:
    """Build the repo-local repeated-measure review artifact for an anno-lab export."""
    context = _load_anno_lab_raw_export_context(source_path)
    review_groups = _build_review_groups(context)
    review_annotation_count = 0
    for group in review_groups:
        annotation_count = group.get("annotation_count")
        if not isinstance(annotation_count, int):
            raise ValueError("review group annotation_count must be an integer")
        review_annotation_count += annotation_count

    return {
        "artifact_kind": ANNO_LAB_REVIEW_GROUPS_ARTIFACT_KIND,
        "artifact_version": ANNO_LAB_REVIEW_GROUPS_ARTIFACT_VERSION,
        "source_contract": ANNO_LAB_RAW_EXPORT_CONTRACT,
        "source_contract_version": ANNO_LAB_RAW_EXPORT_VERSION,
        "normalization_profile": ANNO_LAB_REPEATED_MEASURE_REVIEW_PROFILE,
        "source_export": {
            "source_artifact": context.source_path.name,
            "source_project_id": require_identifier(context.project.get("id"), "project.id"),
            "source_project_slug": require_non_empty_string(
                context.project.get("slug"),
                "project.slug",
            ),
            "source_project_name": require_non_empty_string(
                context.project.get("name"),
                "project.name",
            ),
            "exported_at": context.exported_at,
        },
        "summary": {
            "asset_count": len(context.images),
            "task_count": len(context.tasks_by_id),
            "assignment_count": len(context.assignments_by_id),
            "annotation_record_count": len(context.annotations),
            "review_group_count": len(review_groups),
            "review_annotation_count": review_annotation_count,
            "single_annotation_task_count": len(context.tasks_by_id) - len(review_groups),
        },
        "review_groups": review_groups,
        "notes": [
            (
                "Repeated-measure anno-lab raw groups stay repo-local until "
                "adjudication produces one canonical annotation record per task."
            ),
            (
                "Direct COCO release emission remains fail-closed for tasks "
                "with multiple raw annotation records."
            ),
        ],
    }


def _load_anno_lab_raw_export_context(source_path: str | Path) -> _AnnoLabRawExportContext:
    resolved_source_path = Path(source_path).resolve()
    payload = load_json_object(resolved_source_path)

    export_contract = require_non_empty_string(payload.get("export_contract"), "export_contract")
    if export_contract != ANNO_LAB_RAW_EXPORT_CONTRACT:
        raise ValueError(
            "unsupported anno-lab export_contract "
            f"{export_contract!r}; expected {ANNO_LAB_RAW_EXPORT_CONTRACT!r}"
        )

    export_version = require_non_empty_string(payload.get("export_version"), "export_version")
    if export_version != ANNO_LAB_RAW_EXPORT_VERSION:
        raise ValueError(
            "unsupported anno-lab export_version "
            f"{export_version!r}; expected {ANNO_LAB_RAW_EXPORT_VERSION!r}"
        )

    project = require_object(payload.get("project"), "project")
    summary = require_object(payload.get("summary"), "summary")
    task_types = require_object_list(payload, "task_types")
    task_definitions = require_object_list(payload, "task_definitions")
    assets = require_object_list(payload, "assets")
    tasks = require_object_list(payload, "tasks")
    assignments = require_object_list(payload, "assignments")
    annotations = require_object_list(payload, "annotations")

    _validate_summary_counts(summary, assets, tasks, assignments, annotations)
    task_type_slugs_by_id = _build_task_type_slugs_by_id(task_types)
    task_definitions_by_id = _build_task_definitions_by_id(
        task_definitions,
        task_type_slugs_by_id=task_type_slugs_by_id,
    )
    asset_ids, images = _build_images(assets)
    tasks_by_id = _build_tasks_by_id(
        tasks,
        asset_ids=asset_ids,
        task_definitions_by_id=task_definitions_by_id,
    )
    assignments_by_id = _build_assignments_by_id(assignments, tasks_by_id=tasks_by_id)
    annotation_contexts = _build_annotation_contexts(
        annotations,
        tasks_by_id=tasks_by_id,
        assignments_by_id=assignments_by_id,
    )

    return _AnnoLabRawExportContext(
        source_path=resolved_source_path,
        project=project,
        exported_at=normalize_optional_string(payload.get("exported_at")),
        images=images,
        tasks_by_id=tasks_by_id,
        assignments_by_id=assignments_by_id,
        annotations=annotation_contexts,
        raw_summary={
            "asset_count": len(assets),
            "task_count": len(tasks),
            "assignment_count": len(assignments),
            "annotation_record_count": len(annotations),
        },
    )


def _validate_summary_counts(
    summary: dict[str, object],
    assets: list[dict[str, object]],
    tasks: list[dict[str, object]],
    assignments: list[dict[str, object]],
    annotations: list[dict[str, object]],
) -> None:
    expected_counts = {
        "asset_count": len(assets),
        "task_count": len(tasks),
        "assignment_count": len(assignments),
        "annotation_count": len(annotations),
    }
    for field_name, expected_value in expected_counts.items():
        actual_value = coerce_int(summary.get(field_name), f"summary.{field_name}")
        if actual_value != expected_value:
            raise ValueError(
                f"summary.{field_name} expected {expected_value}, got {actual_value}"
            )


def _build_task_type_slugs_by_id(task_types: list[dict[str, object]]) -> dict[str, str]:
    task_type_slugs_by_id: dict[str, str] = {}
    for index, task_type in enumerate(task_types):
        context = f"task_types[{index}]"
        task_type_id = require_identifier(task_type.get("id"), f"{context}.id")
        if task_type_id in task_type_slugs_by_id:
            raise ValueError(f"duplicate task type id {task_type_id!r}")
        task_type_slugs_by_id[task_type_id] = require_non_empty_string(
            task_type.get("slug"),
            f"{context}.slug",
        )
    return task_type_slugs_by_id


def _build_task_definitions_by_id(
    task_definitions: list[dict[str, object]],
    *,
    task_type_slugs_by_id: dict[str, str],
) -> dict[str, _TaskDefinitionContext]:
    task_definitions_by_id: dict[str, _TaskDefinitionContext] = {}
    for index, task_definition in enumerate(task_definitions):
        context = f"task_definitions[{index}]"
        task_definition_id = require_identifier(task_definition.get("id"), f"{context}.id")
        if task_definition_id in task_definitions_by_id:
            raise ValueError(f"duplicate task definition id {task_definition_id!r}")
        task_type_id = require_identifier(
            task_definition.get("task_type_id"),
            f"{context}.task_type_id",
        )
        task_type_slug = task_type_slugs_by_id.get(task_type_id)
        if task_type_slug is None:
            raise ValueError(
                f"{context}.task_type_id references unknown task type id {task_type_id!r}"
            )
        definition = require_object(task_definition.get("definition"), f"{context}.definition")
        object_classes = _read_object_classes(definition, f"{context}.definition.object_classes")
        task_definitions_by_id[task_definition_id] = _TaskDefinitionContext(
            task_definition_id=task_definition_id,
            task_type_slug=task_type_slug,
            object_classes=object_classes,
        )
    return task_definitions_by_id


def _read_object_classes(definition: dict[str, object], field_name: str) -> tuple[str, ...]:
    raw_labels = definition.get("object_classes")
    if not isinstance(raw_labels, list) or not raw_labels:
        raise ValueError(f"{field_name} must be a non-empty list")
    labels: list[str] = []
    seen_labels: set[str] = set()
    for index, value in enumerate(raw_labels):
        label = require_non_empty_string(value, f"{field_name}[{index}]")
        if label in seen_labels:
            raise ValueError(f"{field_name} contains duplicate label {label!r}")
        seen_labels.add(label)
        labels.append(label)
    return tuple(labels)


def _build_images(
    assets: list[dict[str, object]],
) -> tuple[set[str], tuple[CanonicalImage, ...]]:
    asset_ids: set[str] = set()
    images: list[CanonicalImage] = []
    for index, asset in enumerate(assets):
        context = f"assets[{index}]"
        asset_id = require_identifier(asset.get("id"), f"{context}.id")
        if asset_id in asset_ids:
            raise ValueError(f"duplicate asset id {asset_id!r}")
        media_type = require_non_empty_string(asset.get("media_type"), f"{context}.media_type")
        if media_type != "image":
            raise ValueError(f"{context}.media_type {media_type!r} is not supported yet")
        s3_key = require_non_empty_string(asset.get("s3_key"), f"{context}.s3_key")
        file_name = Path(s3_key).name.strip()
        if not file_name:
            raise ValueError(f"{context}.s3_key must resolve to a file name")
        width = require_positive_int(asset.get("width"), f"{context}.width")
        height = require_positive_int(asset.get("height"), f"{context}.height")
        metadata = coerce_object(asset.get("metadata"))
        split = normalize_optional_string(metadata.get("split"))
        images.append(
            CanonicalImage(
                id=asset_id,
                file_name=file_name,
                width=width,
                height=height,
                source_path_or_uri=s3_key,
                split=split,
            )
        )
        asset_ids.add(asset_id)
    return asset_ids, tuple(images)


def _build_tasks_by_id(
    tasks: list[dict[str, object]],
    *,
    asset_ids: set[str],
    task_definitions_by_id: dict[str, _TaskDefinitionContext],
) -> dict[str, _TaskContext]:
    tasks_by_id: dict[str, _TaskContext] = {}
    for index, task in enumerate(tasks):
        context = f"tasks[{index}]"
        task_id = require_identifier(task.get("id"), f"{context}.id")
        if task_id in tasks_by_id:
            raise ValueError(f"duplicate task id {task_id!r}")
        asset_id = require_identifier(task.get("asset_id"), f"{context}.asset_id")
        if asset_id not in asset_ids:
            raise ValueError(f"{context}.asset_id references unknown asset id {asset_id!r}")
        task_definition_id = require_identifier(
            task.get("task_definition_id"),
            f"{context}.task_definition_id",
        )
        task_definition = task_definitions_by_id.get(task_definition_id)
        if task_definition is None:
            raise ValueError(
                f"{context}.task_definition_id references unknown task definition id "
                f"{task_definition_id!r}"
            )
        if task_definition.task_type_slug not in SUPPORTED_ANNO_LAB_TASK_TYPES:
            supported = ", ".join(SUPPORTED_ANNO_LAB_TASK_TYPES)
            raise ValueError(
                f"{context} uses unsupported task type {task_definition.task_type_slug!r}; "
                f"expected one of {supported}"
            )
        tasks_by_id[task_id] = _TaskContext(
            task_id=task_id,
            asset_id=asset_id,
            task_definition=task_definition,
        )
    return tasks_by_id


def _build_assignments_by_id(
    assignments: list[dict[str, object]],
    *,
    tasks_by_id: dict[str, _TaskContext],
) -> dict[str, _AssignmentContext]:
    assignments_by_id: dict[str, _AssignmentContext] = {}
    for index, assignment in enumerate(assignments):
        context = f"assignments[{index}]"
        assignment_id = require_identifier(assignment.get("id"), f"{context}.id")
        if assignment_id in assignments_by_id:
            raise ValueError(f"duplicate assignment id {assignment_id!r}")
        task_id = require_identifier(assignment.get("task_id"), f"{context}.task_id")
        if task_id not in tasks_by_id:
            raise ValueError(f"{context}.task_id references unknown task id {task_id!r}")
        assignments_by_id[assignment_id] = _AssignmentContext(
            assignment_id=assignment_id,
            task_id=task_id,
            backend=normalize_optional_string(assignment.get("backend")),
            status=normalize_optional_string(assignment.get("status")),
            created_at=normalize_optional_string(assignment.get("created_at")),
            updated_at=normalize_optional_string(assignment.get("updated_at")),
        )
    return assignments_by_id


def _build_annotation_contexts(
    annotations: list[dict[str, object]],
    *,
    tasks_by_id: dict[str, _TaskContext],
    assignments_by_id: dict[str, _AssignmentContext],
) -> tuple[_AnnotationContext, ...]:
    annotation_contexts: list[_AnnotationContext] = []
    seen_annotation_ids: set[str] = set()
    for index, annotation in enumerate(annotations):
        context = f"annotations[{index}]"
        annotation_id = require_identifier(annotation.get("id"), f"{context}.id")
        if annotation_id in seen_annotation_ids:
            raise ValueError(f"duplicate annotation id {annotation_id!r}")
        seen_annotation_ids.add(annotation_id)

        task_id = require_identifier(annotation.get("task_id"), f"{context}.task_id")
        task = tasks_by_id.get(task_id)
        if task is None:
            raise ValueError(f"{context}.task_id references unknown task id {task_id!r}")

        assignment_id = annotation.get("assignment_id")
        normalized_assignment_id: str | None = None
        if assignment_id is not None:
            normalized_assignment_id = require_identifier(
                assignment_id,
                f"{context}.assignment_id",
            )
            if normalized_assignment_id not in assignments_by_id:
                raise ValueError(
                    f"{context}.assignment_id references unknown assignment id "
                    f"{normalized_assignment_id!r}"
                )

        result = require_object(annotation.get("result"), f"{context}.result")
        raw_objects = result.get("objects")
        if not isinstance(raw_objects, list):
            raise ValueError(
                f"{context}.result.objects must be a list for "
                f"{task.task_definition.task_type_slug!r} normalization"
            )

        objects: list[_AnnotationObjectContext] = []
        seen_object_ids: set[str] = set()
        for object_index, raw_object in enumerate(raw_objects):
            object_context = f"{context}.result.objects[{object_index}]"
            if not isinstance(raw_object, dict):
                raise ValueError(f"{object_context} must be an object")
            object_id = require_identifier(raw_object.get("id"), f"{object_context}.id")
            if object_id in seen_object_ids:
                raise ValueError(f"duplicate object id {object_id!r} inside {context}")
            seen_object_ids.add(object_id)
            label = require_non_empty_string(raw_object.get("label"), f"{object_context}.label")
            if label not in task.task_definition.object_classes:
                raise ValueError(
                    f"{object_context}.label {label!r} is not declared in task definition "
                    "object_classes"
                )
            objects.append(
                _AnnotationObjectContext(
                    object_id=object_id,
                    label=label,
                    bbox=_read_bbox_tuple(raw_object.get("bbox"), f"{object_context}.bbox"),
                )
            )

        annotation_contexts.append(
            _AnnotationContext(
                annotation_id=annotation_id,
                task_id=task_id,
                assignment_id=normalized_assignment_id,
                schema_version=normalize_optional_string(annotation.get("schema_version")),
                tool_version=normalize_optional_string(annotation.get("tool_version")),
                submission_id=normalize_optional_string(annotation.get("submission_id")),
                created_at=normalize_optional_string(annotation.get("created_at")),
                objects=tuple(objects),
            )
        )
    return tuple(annotation_contexts)


def _validate_single_annotation_per_task(annotations: tuple[_AnnotationContext, ...]) -> None:
    """Reject exports where any task has more than one annotation record.

    This is the fail-closed boundary for repeated-measure adjudication:
    multi-annotation tasks require an explicit adjudication stage before
    release emission.
    """
    seen_task_ids: set[str] = set()
    for annotation in annotations:
        task_id = annotation.task_id
        if task_id in seen_task_ids:
            raise ValueError(
                "anno-lab raw export contains multiple annotations for one task; "
                "run emit-review-groups before direct release emission"
            )
        seen_task_ids.add(task_id)


def _build_categories(
    tasks_by_id: dict[str, _TaskContext],
) -> tuple[tuple[CanonicalCategory, ...], dict[str, str]]:
    """Deduplicate object-class labels across all tasks into COCO categories.

    Returns the categories tuple and a label-to-category-ID mapping.
    Category IDs are assigned as sequential 1-based integers in encounter order.
    """
    categories: list[CanonicalCategory] = []
    category_ids_by_label: dict[str, str] = {}
    for task in tasks_by_id.values():
        for label in task.task_definition.object_classes:
            if label in category_ids_by_label:
                continue
            category_id = str(len(categories) + 1)
            category_ids_by_label[label] = category_id
            categories.append(
                CanonicalCategory(
                    id=category_id,
                    name=label,
                    supercategory=task.task_definition.task_type_slug,
                )
            )
    return tuple(categories), category_ids_by_label


def _build_annotations(
    annotations: tuple[_AnnotationContext, ...],
    *,
    tasks_by_id: dict[str, _TaskContext],
    category_ids_by_label: dict[str, str],
) -> tuple[dict[str, object], ...]:
    """Convert anno-lab annotation result objects to COCO-format annotations.

    Each ``result.objects[]`` entry becomes a separate COCO annotation with a
    composite ID of ``"{annotation_id}:{object_id}"``.  Provenance fields
    (``anno_lab_annotation_id``, ``anno_lab_task_id``, etc.) are carried as
    sidecar metadata.
    """
    coco_annotations: list[dict[str, object]] = []
    seen_annotation_ids: set[str] = set()
    for annotation in annotations:
        annotation_id = annotation.annotation_id
        task = tasks_by_id.get(annotation.task_id)
        if task is None:
            raise ValueError(
                f"annotation {annotation_id!r} references unknown task id {annotation.task_id!r}"
            )

        for object_candidate in annotation.objects:
            category_id = category_ids_by_label.get(object_candidate.label)
            if category_id is None:
                raise ValueError(
                    f"annotation {annotation_id!r} uses undeclared label "
                    f"{object_candidate.label!r}"
                )
            bbox = list(object_candidate.bbox)
            coco_annotation_id = f"{annotation_id}:{object_candidate.object_id}"
            if coco_annotation_id in seen_annotation_ids:
                raise ValueError(f"duplicate normalized annotation id {coco_annotation_id!r}")
            seen_annotation_ids.add(coco_annotation_id)
            coco_annotation: dict[str, object] = {
                "id": coco_annotation_id,
                "image_id": task.asset_id,
                "category_id": category_id,
                "bbox": bbox,
                "area": round(bbox[2] * bbox[3], 6),
                "iscrowd": 0,
                "anno_lab_annotation_id": annotation_id,
                "anno_lab_task_id": annotation.task_id,
                "source_object_id": object_candidate.object_id,
                "source_task_type": task.task_definition.task_type_slug,
            }
            if annotation.schema_version is not None:
                coco_annotation["anno_lab_schema_version"] = annotation.schema_version
            if annotation.tool_version is not None:
                coco_annotation["anno_lab_tool_version"] = annotation.tool_version
            if annotation.submission_id is not None:
                coco_annotation["anno_lab_submission_id"] = annotation.submission_id
            if annotation.created_at is not None:
                coco_annotation["anno_lab_created_at"] = annotation.created_at
            coco_annotations.append(coco_annotation)
    return tuple(coco_annotations)


def _build_review_groups(
    context: _AnnoLabRawExportContext,
) -> list[dict[str, object]]:
    images_by_id = {image.id: image for image in context.images}
    annotations_by_task: dict[str, list[_AnnotationContext]] = {}
    for annotation in context.annotations:
        annotations_by_task.setdefault(annotation.task_id, []).append(annotation)

    review_groups: list[dict[str, object]] = []
    for task_id, task_annotations in annotations_by_task.items():
        if len(task_annotations) < 2:
            continue
        task = context.tasks_by_id.get(task_id)
        if task is None:
            raise ValueError(f"review group references unknown task id {task_id!r}")
        image = images_by_id.get(task.asset_id)
        if image is None:
            raise ValueError(f"review group references unknown asset id {task.asset_id!r}")

        candidate_annotations: list[dict[str, object]] = []
        for annotation in task_annotations:
            assignment = (
                context.assignments_by_id.get(annotation.assignment_id)
                if annotation.assignment_id is not None
                else None
            )
            candidate_annotations.append(
                {
                    "annotation_id": annotation.annotation_id,
                    "assignment_id": annotation.assignment_id,
                    "assignment_backend": assignment.backend if assignment is not None else None,
                    "assignment_status": assignment.status if assignment is not None else None,
                    "submission_id": annotation.submission_id,
                    "created_at": annotation.created_at,
                    "schema_version": annotation.schema_version,
                    "tool_version": annotation.tool_version,
                    "objects": [
                        {
                            "object_id": object_candidate.object_id,
                            "label": object_candidate.label,
                            "bbox": list(object_candidate.bbox),
                        }
                        for object_candidate in annotation.objects
                    ],
                }
            )

        review_groups.append(
            {
                "group_id": f"task-{task_id}",
                "task_id": task_id,
                "task_definition_id": task.task_definition.task_definition_id,
                "task_type": task.task_definition.task_type_slug,
                "object_classes": list(task.task_definition.object_classes),
                "annotation_count": len(task_annotations),
                "asset": {
                    "asset_id": image.id,
                    "file_name": image.file_name,
                    "width": image.width,
                    "height": image.height,
                    "source_path_or_uri": image.source_path_or_uri,
                    "split": image.split,
                },
                "candidate_annotations": candidate_annotations,
                "notes": [
                    (
                        "Repeated-measure task group; adjudicate to one "
                        "canonical annotation record before COCO release emission."
                    )
                ],
            }
        )
    return review_groups


def _read_bbox_tuple(
    value: object,
    field_name: str,
) -> tuple[float, float, float, float]:
    bbox = _read_bbox(value, field_name)
    return (bbox[0], bbox[1], bbox[2], bbox[3])


def _read_bbox(value: object, field_name: str) -> list[float]:
    """Parse an anno-lab bbox object ``{x, y, width, height}`` into COCO ``[x, y, w, h]``."""
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object with x, y, width, and height")
    x = _coerce_number(value.get("x"), f"{field_name}.x")
    y = _coerce_number(value.get("y"), f"{field_name}.y")
    width = _coerce_number(value.get("width"), f"{field_name}.width")
    height = _coerce_number(value.get("height"), f"{field_name}.height")
    if width < 0 or height < 0:
        raise ValueError(f"{field_name}.width and {field_name}.height must be non-negative")
    return [x, y, width, height]


def _coerce_number(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric")
    return float(value)


def _build_info(
    *,
    project: dict[str, object],
    exported_at: str | None,
) -> dict[str, object]:
    info: dict[str, object] = {
        "description": require_non_empty_string(project.get("name"), "project.name"),
        "dataset_name": require_non_empty_string(project.get("name"), "project.name"),
        "name": require_non_empty_string(project.get("name"), "project.name"),
        "source_project_id": require_identifier(project.get("id"), "project.id"),
        "source_project_slug": require_non_empty_string(project.get("slug"), "project.slug"),
        "source_export_contract": ANNO_LAB_RAW_EXPORT_CONTRACT,
        "source_export_version": ANNO_LAB_RAW_EXPORT_VERSION,
        "normalization_profile": ANNO_LAB_INSTANCE_BBOX_NORMALIZATION_PROFILE,
    }
    project_description = normalize_optional_string(project.get("description"))
    if project_description is not None:
        info["source_project_description"] = project_description
    project_created_at = normalize_optional_string(project.get("created_at"))
    if project_created_at is not None:
        info["source_project_created_at"] = project_created_at
    if exported_at is not None:
        info["source_exported_at"] = exported_at
    return info
