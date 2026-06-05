# Source Format Boundary

`label-lab` is `COCO`-first without being `COCO`-locked.

The runtime now treats source ingestion as an explicit adapter boundary under
`src/label_lab/sources/` instead of letting format-specific parsing leak
through `release.py`.

## Current Support Matrix

| Source format | Adapter family | Release-ready | Notes |
| --- | --- | --- | --- |
| `anno_lab_raw` | `anno-lab-raw` | yes, bounded | current upstream handoff for sanitized `anno-lab` raw exports; repeated-measure tasks stay repo-local review artifacts until adjudicated |
| `COCO` | `coco-family` | yes | current production path for `emit-release` |
| `LabelMe` | `labelme` | yes, bounded | accepts one JSON sidecar or a directory of sidecars; rectangle and polygon shapes only in this tranche |
| `LVIS` | `coco-family` | not yet | boundary declared, adapter intentionally not implemented yet |
| `PASCAL VOC` | legacy adapter | not yet | planned later, outside the current tranche |

## LabelMe Boundary

The LabelMe adapter opens the widest family of common annotation tools
without coupling `label-lab` to any one editor implementation.

Current posture:

- accept either one LabelMe JSON file or a directory containing per-image
  JSON sidecars
- normalize `rectangle` shapes into `bbox` annotations
- normalize `polygon` shapes into segmentation annotations with derived bboxes
- preserve `group_id`, `flags`, and source shape type as explicit annotation
  extension fields
- fail closed on `point`, `circle`, `line`, and `linestrip` shapes until a
  later tranche widens support deliberately
- keep the published v1 release bundle contract unchanged; only the source
  adapter surface widens here

## Anno Lab Raw Boundary

`anno-lab` remains the system of record for annotation capture, provenance, and
raw export. `label-lab` owns downstream ingestion and publication from that raw
handoff.

Current posture:

- the supported upstream contract is `anno_lab_raw_collection_export` `v1.0.0`
- the first release-ready normalization path is bounded to `bbox` /
  `instance_bbox` task families with `result.objects[].bbox`
- repeated-measure exports should materialize via `emit-review-groups` into a
  repo-local review artifact and then `emit-canonical-records` into a
  canonical-record import artifact before any release path widens
- release emission currently fails closed when one task has multiple raw
  annotation records, because repeated-measure adjudication is not part of the
  published bundle path yet
- MTurk worker identifiers and raw assignment payloads should stay in the raw
  source export and out of the public release bundle unless a later
  de-identification path explicitly approves them

## LVIS Boundary

The declared `LVIS` seam is meant to preserve metadata that does not fit the
current v1 published bundle contract without quietly widening that contract.

Planned `LVIS`-specific fields:

- asset-level: `neg_category_ids`, `not_exhaustive_category_ids`
- category-level: `frequency`, `synonyms`, `synset`

Current posture:

- keep the published v1 release bundle stable and `COCO`-compatible
- keep `LVIS`-only fields in explicit sidecars or extended records until the
  contract changes deliberately
- fail closed if code attempts to treat `LVIS` as release-ready before the
  adapter lands
