# label-lab

Dataset engineering framework for deterministic ingestion, cleaning, release
packaging, and analysis.

A framework-oriented repository for turning heterogeneous annotation exports
into auditable dataset releases that can be validated, published, and reused
over time.

## Design Intent

`label-lab` is designed as a research instrument, not a one-off conversion
script.

It is meant to support:

- explicit source adapters instead of hidden format assumptions
- one canonical dataset model before release packaging hardens
- deterministic cleaning and quality-review passes
- artifact-backed dataset publication and later audit
- long-lived format evolution without mutating accepted historical outputs

Key principle:

- source formats adapt into one canonical dataset surface, then release
  packaging hardens around that normalized representation

## Repo Map

- `src/label_lab/`: active Python runtime for adapters, normalization, and
  release emission
- `tests/`: runtime and CLI validation surface
- `artifacts/`: persisted output surface for cleaned datasets, reports, and
  release bundles
- `docs/README.md`: docs index
- `docs/architecture.md`: runtime map and format posture
- `docs/source_formats.md`: current source-adapter support matrix
- `docs/runbooks.md`: setup, validation, and release-emission guide

## 60-Second Setup

1. Use a Python environment that already contains the repo dependencies.
On declaratively managed workstations, no repo-local `.venv` is required.

```bash
just setup
```

2. Run the baseline validation passes.

```bash
just lint
just typecheck
just test
```

3. Emit a release bundle from a supported source export.

```bash
PYTHONPATH=src python -m label_lab.main emit-release \
  --source-coco /path/to/annotations.json \
  --output-dir artifacts/releases/demo \
  --release-version 0.1.0
```

Or from a bounded `anno-lab` raw export:

```bash
PYTHONPATH=src python -m label_lab.main emit-release \
  --source-anno-lab-raw /path/to/raw_collection_export.json \
  --output-dir artifacts/releases/demo-anno-lab-raw \
  --release-version 0.1.0
```

Or from LabelMe JSON sidecars:

```bash
PYTHONPATH=src python -m label_lab.main emit-release \
  --source-labelme /path/to/labelme-sidecars \
  --output-dir artifacts/releases/demo-labelme \
  --release-version 0.1.0
```

For repeated-measure `anno-lab` raw exports, emit the repo-local review
artifact instead of a release bundle:

```bash
PYTHONPATH=src python -m label_lab.main emit-review-groups \
  --source-anno-lab-raw /path/to/repeated_measure_export.json \
  --output-path artifacts/reviews/demo-anno-lab-raw-review-groups.json
```

Then import adjudicated selections into a canonical-record artifact:

```bash
PYTHONPATH=src python -m label_lab.main emit-canonical-records \
  --review-groups artifacts/reviews/demo-anno-lab-raw-review-groups.json \
  --adjudication /path/to/review_adjudication.json \
  --output-path artifacts/reviews/demo-anno-lab-raw-canonical-records.json
```

## How It Works

```text
Source Adapter -> Canonical Dataset Model -> Deterministic Cleaning / Analysis -> Release Bundle
```

- source adapters normalize incoming exports into stable dataset records
- cleaning and analysis operate on canonical records instead of raw format quirks
- release emission writes a manifest-backed bundle for downstream use

## Current Runtime Surfaces

- a public `emit-release` CLI for COCO-first bundle emission from direct `COCO`
  inputs, bounded `anno-lab` raw exports, or LabelMe JSON sidecars, plus a
  repo-local `emit-review-groups` CLI and `emit-canonical-records` CLI for
  repeated-measure `anno_lab_raw` adjudication artifacts
- an explicit `sources/` adapter boundary with release-ready `COCO`,
  `anno_lab_raw`, and `labelme` inputs while `LVIS` remains planned but
  fail-closed
- manifest-backed releases that currently write `release_manifest.json` plus
  `annotations.coco.json`
- `src/label_lab/release_contract.py` as the public producer authority for the
  emitted bundle contract and artifact names
- an active Python runtime under `src/label_lab/`
- an artifact surface under `artifacts/` for reproducible generated outputs
- a checked-in minimal contract fixture under
  `tests/fixtures/published_release_bundle_v1/` for bundle-regression coverage

## Current Focus

- harden `anno-lab` raw-export ingestion without pulling raw-export logic back
  into `anno-lab`
- keep repeated-measure adjudication explicit and repo-local before widening
  source support or publication semantics
- expand adapter seams for `YOLO`, `LVIS`, and `PASCAL VOC` after the LabelMe
  path is stable
- add richer provenance, quality-review, and analysis sidecars without
  distorting the base publication contract

## Safety Posture

- preserve source provenance and deterministic transform identity
- fail closed when geometry or metadata semantics are ambiguous
- keep richer metadata in explicit sidecars instead of overloading raw `COCO`
  objects
- keep `.env.example` placeholder-only
- treat historical artifacts as additive, not mutable

## Docs Map

- `docs/README.md`: docs index
- `docs/architecture.md`: architecture, runtime seams, and format posture
- `docs/source_formats.md`: source-adapter support matrix and raw-export /
  `LVIS` boundaries
- `docs/runbooks.md`: bootstrap, validation, and release-emission reference
- `artifacts/README.md`: artifact-output guidance

## License

This project is licensed under the MIT License. See `LICENSE` for the full
text.
