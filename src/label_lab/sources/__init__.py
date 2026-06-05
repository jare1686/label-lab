"""Source adapter boundary: format-specific loaders, contracts, and registry."""

from label_lab.models import CanonicalCategory, CanonicalImage
from label_lab.sources.anno_lab_raw import load_anno_lab_raw_source_dataset
from label_lab.sources.coco import build_split_summary, infer_task_types, load_coco_source_dataset
from label_lab.sources.contracts import SourceDataset, SourceFormatBoundary
from label_lab.sources.labelme import load_labelme_source_dataset
from label_lab.sources.registry import (
    get_source_format_boundary,
    list_source_format_boundaries,
    load_source_dataset,
)

__all__ = [
    "CanonicalCategory",
    "CanonicalImage",
    "SourceDataset",
    "SourceFormatBoundary",
    "build_split_summary",
    "get_source_format_boundary",
    "infer_task_types",
    "list_source_format_boundaries",
    "load_anno_lab_raw_source_dataset",
    "load_coco_source_dataset",
    "load_labelme_source_dataset",
    "load_source_dataset",
]
