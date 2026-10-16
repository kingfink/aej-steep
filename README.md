# aej-steep

Steep semantic-layer definitions created for [Analytics Engineering Jobs](https://www.analyticsengineeringjobs.com/).

This repository is published as a small reference and showcase of defining metrics in code with [Steep](https://steep.app/). It is maintained for my own use; issues and pull requests are not accepted.

## Models

- [`dim_jobs.yml`](dim_jobs.yml) defines PII-safe job dimensions, including level, role type, and remote status, the join paths that rank jobs by form submissions, on-site traffic, apply clicks, newsletter link clicks, and search performance and that count listed jobs, and the Job entity for drilling from those metrics to job records.
- [`fct_jobs_daily.yml`](fct_jobs_daily.yml) defines listed-job counts, usable USD salary coverage, and approximate posted-range midpoint median and 25th/75th percentiles as of the latest date in the range. Percentiles use BigQuery `approx_quantiles` for simplicity.
- [`dim_organizations.yml`](dim_organizations.yml) defines PII-safe organization dimensions, the join paths to form submissions, on-site web events, and search performance, and the Organization entity.
- [`dim_web_sessions.yml`](dim_web_sessions.yml) defines session acquisition, browser, device, and country dimensions and the join paths to session outcomes, web events, and form submissions.
- [`dim_pages.yml`](dim_pages.yml) defines page path and page type dimensions, the join paths to web events and URL-level search performance, so on-site traffic and search demand slice by the same page, and the Page entity.
- [`dim_countries.yml`](dim_countries.yml) defines country and continent dimensions and the join paths to URL-level and site-level search performance.
- [`dim_email_messages.yml`](dim_email_messages.yml) defines shared provider and subject dimensions for message and event metrics, and the Email Message entity.
- [`dim_email_campaigns.yml`](dim_email_campaigns.yml) defines newsletter-issue dimensions, including campaign name, subject, send date, and the test-send flag, and the Email Campaign entity.
- [`dim_email_subscribers.yml`](dim_email_subscribers.yml) defines subscriber join paths and PII-safe entity drill-downs.
- [`fct_web_events.yml`](fct_web_events.yml) defines page-view, apply-click, visitor, and apply-click-rate metrics for on-site job popularity, joined to job, organization, session channel, and page dimensions, plus page view attribution coverage.
- [`fct_web_sessions.yml`](fct_web_sessions.yml) defines the provisional engaged job-seeker session outcome and session apply-rate guardrail, with no geography, browser, or device exclusion.
- [`fct_form_submissions.yml`](fct_form_submissions.yml) defines submission and known-submitter metrics, canonical form slices, and joined subscriber, job, organization, and session channel dimensions, plus form submission attribution coverage.
- [`fct_search_performance.yml`](fct_search_performance.yml) defines URL-level Search Console impressions, clicks, click-through rate, and average position, joined to page, country, job, and organization dimensions.
- [`fct_search_performance_site.yml`](fct_search_performance_site.yml) defines property-level Search Console impressions, clicks, click-through rate, and best-result average position. It is deliberately kept separate from the URL-level module because property totals are lower than URL totals.
- [`fct_email_subscribers_daily.yml`](fct_email_subscribers_daily.yml) defines the historical subscriber-population metric.
- [`fct_email_events.yml`](fct_email_events.yml) defines event activity, acquisition-cohort analysis, unique engaged-subscriber metrics, and newsletter link-click metrics resolved to the job each link points at.
- [`fct_email_subscriber_messages.yml`](fct_email_subscriber_messages.yml) defines subscriber-message outcomes and delivery, open, and click rates.
- [`fct_events.yml`](fct_events.yml) defines a Steep module and event-count metric for GA4 events. It depends on legacy SQLMesh models and is scheduled for deprecation, but is retained here as an example of the original semantic-layer implementation.

[`targets.yml.example`](targets.yml.example) contains the Steep target-table registration to enable after the corresponding warehouse table has been created and populated. The intended table is `dbt_prd.email_metric_targets`; it should contain targets for `email_subscribers`, `email_delivery_rate`, `email_open_rate`, and `email_click_rate`. Ratio targets require numerator and denominator values in addition to the displayed target value.

Current Analytics Engineering Jobs transformations live in [aej-dbt](https://github.com/kingfink/aej-dbt).

For automation-safe job lookups, use `Organization Slug` and `Job Slug` together. The pair maps directly to `docs/jobs/{organization_slug}/{job_slug}.md`; organization names and job titles are display labels and may change.

This is not a standalone project. The underlying warehouse models, data, credentials, and Steep workspace are not included.

## Validation and previews

Install the development dependencies once:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

Run the same checks as CI:

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/validate.py
```

The command lints and parses the root-level definitions, then sends them to Steep's credential-free [`/v1/code/validate`](https://help.steep.app/api) endpoint for structure, identifier, breakdown-dimension, and cohort checks. It fails on API errors, malformed responses, or reported problems, including warnings. No separate schema download, local schema copy, or custom semantic graph engine is maintained. The command requires network access; the focused unit tests do not.

Local safeguards cover gaps in that endpoint: AEJ datasets (including legacy `marts`), module roles, join-target and entity-metric existence, qualified-reference schemas, derived operands and slices, and the known derived-ratio/last-date failure. The targets example is sent under a synthetic `.yml` filename for validation only; it is never registered or included in a sync preview. Workflows and tests are excluded.

Join reachability and derived-metric cycles remain review and post-sync verification responsibilities. Neither the public endpoint nor these focused checks verifies warehouse columns, types, freshness, keys, grain, or generated-query correctness. Avoid treating a successful pre-merge check as runtime validation.

For a workspace-aware preview, configure `STEEP_API_KEY` and `STEEP_DATASOURCE_ID` in your environment, using an AEJ-scoped credential with the permissions required by the code sync endpoint, then run:

```sh
.venv/bin/python scripts/validate.py --preview
```

This always sends `dryRun: true` with the complete active model and prints the proposed creations, updates, removals, errors, and warnings. It never applies or queues a sync. Inspect removals before merging. The command fails if credentials are missing or if the preview reports errors, warnings, or an unexpected response. Confirm the datasource belongs to AEJ before configuring it.

The GitHub Actions workflow runs local and public API checks on pull requests and pushes to `master`. Its manual **preview** option additionally uses the repository secret `STEEP_API_KEY` and repository variable `STEEP_DATASOURCE_ID`; this authenticated step does not run on pull requests. Setting up these values remains an operator action. After merge and Steep sync, query affected metrics and at least one joined dimension through the AEJ Steep MCP.

For editor validation and autocomplete, `.vscode/settings.json` centrally associates root-level `dim_*.yml` and `fct_*.yml` files with the module schema, and `targets.yml` and `targets.yml.example` with the targets schema. It also opens the example in YAML mode. These settings work in VS Code and Cursor with the Red Hat YAML extension; other editors can use the same schema URLs in their language-server configuration.

## Rights

No open-source license is granted. All rights reserved.
