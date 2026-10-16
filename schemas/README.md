# Steep schema snapshots

`module.json` and `targets.json` are unmodified JSON Schemas downloaded from Steep on October 16, 2026. Local validation uses these snapshots so it works without a network connection and schema changes enter through a reviewed diff. Editor comments use the live schemas.

- Module source: https://api.steep.app/v1/code/schema/module
- Targets source: https://api.steep.app/v1/code/schema/targets

To refresh, download both files from those URLs, run the regression tests and local validation, then review the schema changes. Do not replace the repository-specific checks with JSON Schema validation: the schemas cannot resolve our semantic graph or confirm warehouse contracts.
