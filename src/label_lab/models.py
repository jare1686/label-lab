"""Typed canonical models for images and categories across all source adapters.

:class:`CanonicalImage` and :class:`CanonicalCategory` provide a typed
intermediate representation that eliminates raw-dict manipulation in
downstream code.  Annotations remain as ``dict[str, object]`` because
each adapter adds different sidecar fields.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CanonicalImage:
    """Validated image record normalized by a source adapter.

    All identifiers are stored as strings for uniformity across adapters.
    ``source_path_or_uri`` carries the resolved path or URL to the asset;
    the COCO adapter populates this from ``coco_url`` when present.
    """

    id: str
    file_name: str
    width: int
    height: int
    source_path_or_uri: str
    split: str | None = None

    def to_coco_dict(self) -> dict[str, object]:
        """Serialize to a COCO-compatible image dict."""
        result: dict[str, object] = {
            "id": self.id,
            "file_name": self.file_name,
            "width": self.width,
            "height": self.height,
            "source_path_or_uri": self.source_path_or_uri,
        }
        if self.split is not None:
            result["split"] = self.split
        return result

    def to_asset_row(self, dataset_id: str) -> dict[str, object]:
        """Serialize to a flat asset row for the Parquet sidecar table."""
        return {
            "asset_id": self.id,
            "dataset_id": dataset_id,
            "file_name": self.file_name,
            "width": self.width,
            "height": self.height,
            "media_type": "image",
            "source_asset_id": self.id,
            "source_path_or_uri": self.source_path_or_uri,
            "split": self.split or "unspecified",
        }


@dataclass(frozen=True, slots=True)
class CanonicalCategory:
    """Validated category record normalized by a source adapter."""

    id: str
    name: str
    supercategory: str | None = None

    def to_coco_dict(self) -> dict[str, object]:
        """Serialize to a COCO-compatible category dict."""
        result: dict[str, object] = {
            "id": self.id,
            "name": self.name,
        }
        if self.supercategory is not None:
            result["supercategory"] = self.supercategory
        return result

    def to_category_row(self, dataset_id: str) -> dict[str, object]:
        """Serialize to a flat category row for the Parquet sidecar table."""
        return {
            "category_id": self.id,
            "dataset_id": dataset_id,
            "name": self.name,
            "source_category_id": self.id,
            "supercategory": self.supercategory or "",
        }
