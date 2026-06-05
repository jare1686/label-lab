# Architecture

## Intent

`label-lab` is a standalone framework for turning heterogeneous annotation and
dataset exports into a canonical intermediate representation that can be
cleaned, analyzed, and repackaged without mutating source truth.

The framework is deliberately data-agnostic. The immediate format strategy is
`COCO`-first, with release-ready `anno-lab` raw-export and `labelme`
adapters, a repo-local repeated-measure review-artifact path, and explicit
planned adapter paths for `LVIS` and `PASCAL VOC`.

## Repository Layers

### Runtime

`src/label_lab/` is the active Python runtime. The current runtime now
separates release emission from source parsing:

- `src/label_lab/release.py`: bundle writer and manifest emission
- `src/label_lab/release_contract.py`: explicit v1 manifest and artifact-name
  helpers
- `src/label_lab/sources/`: source-adapter boundary and support matrix
- `src/label_lab/adjudication.py`: repo-local repeated-measure review-artifact
  emission and canonical-record import artifact emission for `anno_lab_raw`

Producer authority note:

- `src/label_lab/release_contract.py` is the public producer authority for the
  emitted `release_manifest.json` shape, bundle kind, and required artifact
  names
- downstream repos should consume the declared bundle contract instead of
  relying on private `label-lab` implementation details

### Runtime Shape

`label-lab` centers on ingestion, deterministic cleaning, dataset analysis,
and publication packaging.

The runtime uses:

- explicit adapters for incoming source data
- normalized source datasets as the release-writer input
- release artifacts as the exported runtime output

### Artifacts

`artifacts/` is the future evidence surface for cleaned datasets, benchmark
exports, quality reports, analysis results, and release bundles.

The checked-in regression seam for the current release contract lives under
`tests/fixtures/`:

- `tests/fixtures/demo_source_coco.json`
- `tests/fixtures/published_release_bundle_v1/`

### Format Posture

`label-lab` should not hard-code one source format as its center of gravity.

Instead:

- `anno-lab` raw exports should enter through an explicit `anno_lab_raw`
  adapter in `label-lab`, not through source-specific `COCO` generation inside
  `anno-lab`
- LabelMe JSON sidecars should enter through the standalone `labelme` adapter
  so LabelMe, AnyLabeling, and X-AnyLabeling exports share one bounded path
- `COCO` is the canonical publication contract and the first-class
  interoperable format
- `LVIS` should map through the same `coco-family` adapter seam with preserved
  long-tail metadata
- `PASCAL VOC` should be supported through a stricter legacy adapter later
- if a source already publishes `COCO`, it should flow through the same
  adapter path rather than a source-specific ingestion mode

The current release writer is intentionally fail-closed:

- direct `COCO`, bounded `anno_lab_raw`, and bounded `labelme` rectangle /
  polygon paths are release-ready today
- `anno_lab_raw` release emission is intentionally limited to one annotation
  record per task until repeated-measure ingestion and adjudication harden
- `labelme` support is intentionally limited to rectangle and polygon shape
  types; point, circle, line, and linestrip remain out of contract until a
  later tranche widens the adapter
- repeated-measure `anno_lab_raw` task groups should materialize as an
  explicit review artifact and adjudicated canonical-record import artifact
  before they become canonical release records
- `LVIS` is declared in the runtime support matrix but not yet implemented as
  a release-ready adapter
- attempts to treat `LVIS` as release-ready should fail explicitly until the
  adapter lands

## Realized Module Seams

The runtime now has these actual seams on disk:

- `sources/`: format and source adapters plus the support matrix
- `release.py`: bundle emission from a normalized source dataset
- `release_contract.py`: v1 bundle manifest and artifact naming
- `adjudication.py`: review-group emission and canonical-record import artifact
  emission for repeated-measure raw exports

Planned downstream seams still remain:

- `models/`: canonical dataset, split, asset, and annotation contracts
- `cleaning/`: deterministic transforms and quality checks
- `analysis/`: geometry, clutter, reliability, and agreement analysis helpers
- `converters/`: benchmark and external format packaging
- `reports/`: dataset cards, summary tables, and manifest-backed outputs

## Current Domain Requirements

The release format should support:

- object annotations with explicit geometry and category context
- scene-level or asset-level response records
- split, asset, and source-level metadata for later audit
- repeated-measure, agreement, and quality-review inputs
- image-source lineage across MS-COCO, PACO, Ego4D frames, and other source
  datasets
- scene-complexity and clutter metrics
- benchmark-ready splits, release artifacts, and publication-ready handoff
  bundles for evaluation workflows
