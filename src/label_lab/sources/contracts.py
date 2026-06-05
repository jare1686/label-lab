"""Immutable data contracts shared across all source adapters.

:class:`SourceFormatBoundary` declares what a format adapter supports before
loading begins.  :class:`SourceDataset` carries the validated, normalized
output of a successful adapter load.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from label_lab.models import CanonicalCategory, CanonicalImage


def _require_non_empty_string(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class SourceFormatBoundary:
    """Declared capability boundary for a source format adapter.

    ``release_ready`` indicates whether the adapter can produce bundles suitable
    for publication.  Extension field tuples declare format-specific fields that
    the adapter may add beyond the base COCO schema.
    """

    source_format: str
    adapter_family: str
    release_ready: bool
    asset_extension_fields: tuple[str, ...] = ()
    category_extension_fields: tuple[str, ...] = ()
    annotation_extension_fields: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty_string(self.source_format, "source_format")
        _require_non_empty_string(self.adapter_family, "adapter_family")
        for index, field_name in enumerate(self.asset_extension_fields):
            _require_non_empty_string(field_name, f"asset_extension_fields[{index}]")
        for index, field_name in enumerate(self.category_extension_fields):
            _require_non_empty_string(field_name, f"category_extension_fields[{index}]")
        for index, field_name in enumerate(self.annotation_extension_fields):
            _require_non_empty_string(field_name, f"annotation_extension_fields[{index}]")
        for index, note in enumerate(self.notes):
            _require_non_empty_string(note, f"notes[{index}]")

    def to_dict(self) -> dict[str, object]:
        return {
            "source_format": self.source_format,
            "adapter_family": self.adapter_family,
            "release_ready": self.release_ready,
            "asset_extension_fields": list(self.asset_extension_fields),
            "category_extension_fields": list(self.category_extension_fields),
            "annotation_extension_fields": list(self.annotation_extension_fields),
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class SourceDataset:
    """Validated and normalized dataset loaded by a source adapter.

    All adapters produce typed :class:`CanonicalImage` and
    :class:`CanonicalCategory` tuples alongside raw annotation dicts.
    The COCO payload is derived on demand via :meth:`build_coco_payload`
    rather than stored alongside the typed models.
    """

    source_format: str
    source_path: Path
    info: dict[str, object]
    images: tuple[CanonicalImage, ...]
    categories: tuple[CanonicalCategory, ...]
    annotations: tuple[dict[str, object], ...]
    adapter_metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_string(self.source_format, "source_format")
        if not self.source_path.is_absolute():
            raise ValueError("source_path must be absolute")

    def build_coco_payload(self) -> dict[str, object]:
        """Build a COCO-compatible annotation payload from the typed models."""
        return {
            "info": self.info,
            "images": [image.to_coco_dict() for image in self.images],
            "categories": [category.to_coco_dict() for category in self.categories],
            "annotations": list(self.annotations),
        }

    def counts(self) -> dict[str, int]:
        return {
            "asset_count": len(self.images),
            "annotation_count": len(self.annotations),
            "category_count": len(self.categories),
        }
