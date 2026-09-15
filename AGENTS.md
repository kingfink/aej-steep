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

## Module roles

- Fact modules (`fct_*.yml`) hold metrics and the dimensions that exist only on that fact, such as a search query or a link type.
- Dimension modules (`dim_*.yml`) hold descriptive dimensions, entities, and join paths. Never define metrics on a dimension module.
- A dimension holds current state only. To count dimension records over time, such as active jobs or subscribers by month, add a snapshot fact first, as `fct_email_subscribers_daily` does for subscribers.
- Declare each join path once, on the "one" side of the relationship, with `type: "one-to-many"` (or `"one-to-one"` when it truly is). In this repository that is always the dimension, including dimension-to-dimension joins such as `dim_email_campaigns` to `dim_email_messages`. Steep's code reference allows only `one-to-one` and `one-to-many`, so a fact-side `many-to-one` join cannot be expressed, and a declared join is usable from both sides.
- Steep follows join paths at most two steps away. A metric or entity that needs a table three steps away needs a more direct join.
- Use `approx_quantiles` for median and percentile metrics for simplicity. A `custom-value` expression is an aggregate inside Steep's own `group by`, and BigQuery offers `percentile_cont` only as a window function. Describe these metrics as approximate.

## Entities

- Define entities only on dimension modules (`dim_*.yml`), never on fact modules. An entity is the record-level view of a dimension, so a drill-down from a dimension value lists the records that value describes.
- If a drill-down needs records that no dimension describes, add the dimension first. Not every dimension needs an entity.
- Use only `icon_name` values from the supported icon list in [Steep's code reference](https://help.steep.app/setup-and-manage/code-reference). An unsupported name syncs with a warning, not an error, and falls back to a default icon. `building`, `file`, and `send` are not supported; check the list rather than guessing a common icon name.
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
