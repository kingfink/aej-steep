# aej-steep

Steep semantic-layer definitions created for [Analytics Engineering Jobs](https://www.analyticsengineeringjobs.com/).

This repository is published as a small reference and showcase of defining metrics in code with [Steep](https://steep.app/). It is maintained for my own use; issues and pull requests are not accepted.

## Models

- [`dim_jobs.yml`](dim_jobs.yml) defines PII-safe job dimensions, including level, role type, and remote status, the join paths that rank jobs by form submissions, on-site traffic, apply clicks, newsletter link clicks, and search performance and that count listed jobs, and the Job entity for drilling from those metrics to job records.
- [`fct_jobs_daily.yml`](fct_jobs_daily.yml) defines listed-job counts, usable USD salary coverage, and posted-range midpoint median and 25th/75th percentiles as of the latest date in the range.
- [`dim_organizations.yml`](dim_organizations.yml) defines PII-safe organization dimensions, the join paths to form submissions, on-site web events, and search performance, and the Organization entity.
- [`dim_web_sessions.yml`](dim_web_sessions.yml) defines session acquisition channel and entry attribution dimensions and the join paths to web events and form submissions.
- [`dim_pages.yml`](dim_pages.yml) defines page path and page type dimensions, the join paths to web events and URL-level search performance, so on-site traffic and search demand slice by the same page, and the Page entity.
- [`dim_countries.yml`](dim_countries.yml) defines country and continent dimensions and the join paths to URL-level and site-level search performance.
- [`dim_email_messages.yml`](dim_email_messages.yml) defines shared provider and subject dimensions for message and event metrics, and the Email Message entity.
- [`dim_email_campaigns.yml`](dim_email_campaigns.yml) defines newsletter-issue dimensions, including campaign name, subject, send date, and the test-send flag, and the Email Campaign entity.
- [`dim_email_subscribers.yml`](dim_email_subscribers.yml) defines subscriber join paths and PII-safe entity drill-downs.
- [`fct_web_events.yml`](fct_web_events.yml) defines page-view, apply-click, visitor, and apply-click-rate metrics for on-site job popularity, joined to job, organization, session channel, and page dimensions, plus page view attribution coverage.
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

## Rights

No open-source license is granted. All rights reserved.
