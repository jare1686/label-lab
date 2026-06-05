# Docs Index

Use this folder for:

- architecture and dataset-release references
- setup, validation, and operator runbooks
- format-posture notes for the current COCO-first publication seam

Active runtime note:

- `src/label_lab/` is the active Python runtime tree
- `emit-release` is the public release-bundle CLI
- `emit-review-groups` and `emit-canonical-records` are repo-local
  repeated-measure adjudication CLIs
- `artifacts/` is the persisted output surface for release bundles and related
  generated evidence
- `tests/fixtures/published_release_bundle_v1/` is the checked-in minimal
  release fixture for contract-regression coverage
- `src/label_lab/sources/` is the explicit source-adapter boundary for
  `anno_lab_raw`, `COCO`, `labelme`, and future `LVIS` / `PASCAL VOC` support

Validation note:

- the default validation commands are `just lint`, `just typecheck`, and
  `just test`
- `docs/runbooks.md` is the detailed setup and validation guide

Current high-value docs:

- `docs/architecture.md`
- `docs/runbooks.md`
- `docs/source_formats.md`
