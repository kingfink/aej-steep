# Repository guidance

## Project scope

- This repository contains Steep semantic-layer definitions for Analytics Engineering Jobs.
- It is a public reference and showcase maintained for the owner's use. Do not add contribution-oriented scaffolding unless explicitly requested.
- Current transformations and warehouse contracts live in `kingfink/aej-dbt`.

## Source contracts

- Current email, site-content, and web-engagement models are produced by `aej-dbt` in the `dbt_prd` dataset.
- `fct_events.yml` is a legacy SQLMesh definition and remains on `marts`.
- Before adding or changing a module, verify its production dataset, table, columns, keys, and grain against the current upstream dbt model and contract.
- Do not infer a warehouse dataset from a dbt model-directory name.
- `targets.yml.example` is documentation only. Do not treat it as an active Steep targets registration.
- Keep PII, including subscriber email addresses, out of Steep definitions.

## Entities

- Define entities only on dimension modules (`dim_*.yml`), never on fact modules. An entity is the record-level view of a dimension, so a drill-down from a dimension value lists the records that value describes.
- If a drill-down needs records that no dimension describes, add the dimension first. Not every dimension needs an entity.
- Use only `icon_name` values confirmed by a warning-free Steep sync: `briefcase`, `mail`, and `user`. Steep accepts only its own kebab-case icon names, and an unsupported name syncs with a warning rather than an error. `building`, `file`, and `send` are known to be unsupported. Add a name to the confirmed list only after checking Steep sync history.
- Link an entity only to listed metrics whose table is reachable from the entity's table through declared join paths. Prefer metrics that already carry the entity's dimension, so the drill-down matches the breakdown.

## Validation

- Before committing a YAML change, parse all definitions and run every available repository check. Once the validator tracked in issue #3 is added, it is required for every YAML change.
- YAML parsing alone is not sufficient evidence of semantic or runtime validity.
- Qualified dimensions, cohorts, derived metrics, joins, and entity metric references must resolve within the local semantic graph.
- A cohort time dimension must be declared as a `time` dimension on the referenced module. An entity property alone is insufficient.
- Every newly encountered, locally detectable Steep sync failure must produce a regression test before or alongside its fix so the same failure does not recur.
- If a failure depends on warehouse state and cannot be checked generically, add a narrow repository contract test or document the invariant here.
- After Steep syncs, use the Steep MCP to query the affected metrics and at least one joined dimension. Do not report runtime validation based only on YAML parsing.

## Workflow

- Refresh `master` from the remote before starting and use a feature branch and pull request. Do not push changes directly to `master`.
- Use connector tools first for GitHub, Steep, warehouse discovery, status, metadata, logs, and comments. Use CLI or API shell fallbacks only when the required connector action is unavailable or lacks permission.
- Keep changes focused and update documentation when behavior or local commands change.
- Report the exact checks run and distinguish local validation from post-sync Steep verification.
