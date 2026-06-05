# Development Runbook

## Bootstrap

```bash
just setup
```

Manual equivalent:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .[dev]
```

## Validation

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy src
.venv/bin/python -m pytest -q
```

## Checked-In Contract Fixture

- source payload fixture: `tests/fixtures/demo_anno_lab_raw_export.json`
- source payload fixture: `tests/fixtures/demo_anno_lab_raw_repeated_measure_export.json`
- adjudication fixture: `tests/fixtures/demo_anno_lab_raw_review_adjudication.json`
- source payload fixture: `tests/fixtures/demo_source_coco.json`
- source payload fixture: `tests/fixtures/demo_source_labelme/`
- emitted bundle fixture: `tests/fixtures/published_release_bundle_v1/`
- use the fixture to catch manifest or artifact drift before widening the
  contract or adding new source adapters

Exercise the LabelMe adapter with:

```bash
.venv/bin/python -m label_lab emit-release \
  --source-labelme tests/fixtures/demo_source_labelme \
  --output-dir artifacts/releases/demo-labelme \
  --release-version 0.5.0
```

Exercise the bounded `anno-lab` raw adapter with:

```bash
.venv/bin/python -m label_lab emit-release \
  --source-anno-lab-raw tests/fixtures/demo_anno_lab_raw_export.json \
  --output-dir artifacts/releases/demo-anno-lab-raw \
  --release-version 0.4.0
```

Exercise the repeated-measure review path with:

```bash
.venv/bin/python -m label_lab emit-review-groups \
  --source-anno-lab-raw tests/fixtures/demo_anno_lab_raw_repeated_measure_export.json \
  --output-path artifacts/reviews/demo-anno-lab-raw-review-groups.json
```

Exercise the canonical-record import path with:

```bash
.venv/bin/python -m label_lab emit-canonical-records \
  --review-groups artifacts/reviews/demo-anno-lab-raw-review-groups.json \
  --adjudication tests/fixtures/demo_anno_lab_raw_review_adjudication.json \
  --output-path artifacts/reviews/demo-anno-lab-raw-canonical-records.json
```

Regenerate the fixture with:

```bash
.venv/bin/python -m label_lab emit-release \
  --source-coco tests/fixtures/demo_source_coco.json \
  --output-dir tests/fixtures/published_release_bundle_v1 \
  --release-version 1.2.0
```

## Current Runtime Notes

- the current release path emits `release_manifest.json` plus `annotations.coco.json`
- source ingestion now enters through `src/label_lab/sources/`
- `labelme` accepts either one JSON sidecar file or a directory of per-image
  JSON sidecars, but only rectangle and polygon shapes are release-ready in
  this tranche
- `anno_lab_raw` is release-ready only for a bounded `instance_bbox` / `bbox`
  normalization path with one annotation record per task
- repeated-measure `anno_lab_raw` task groups should go through
  `emit-review-groups` and `emit-canonical-records` before any adjudicated
  release path is introduced
- keep richer dataset metadata in sidecar-friendly records instead of forcing everything into raw `COCO` objects
- keep non-COCO sources behind explicit adapter boundaries
