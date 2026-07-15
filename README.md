# aej-steep

Steep semantic-layer definitions created for [Analytics Engineering Jobs](https://www.analyticsengineeringjobs.com/).

This repository is published as a small reference and showcase of defining metrics in code with [Steep](https://steep.app/). It is maintained for my own use; issues and pull requests are not accepted.

## Models

- [`dim_email_messages.yml`](dim_email_messages.yml) defines shared provider and subject dimensions for message and event metrics.
- [`dim_email_subscribers.yml`](dim_email_subscribers.yml) defines subscriber join paths and PII-safe entity drill-downs.
- [`fct_email_subscribers_daily.yml`](fct_email_subscribers_daily.yml) defines the historical subscriber-population metric.
- [`fct_email_events.yml`](fct_email_events.yml) defines event activity, acquisition-cohort analysis, and unique engaged-subscriber metrics.
- [`fct_email_subscriber_messages.yml`](fct_email_subscriber_messages.yml) defines subscriber-message outcomes, entity drill-downs, and delivery, open, and click rates.
- [`fct_events.yml`](fct_events.yml) defines a Steep module and event-count metric for GA4 events. It depends on legacy SQLMesh models and is scheduled for deprecation, but is retained here as an example of the original semantic-layer implementation.

[`targets.yml.example`](targets.yml.example) contains the Steep target-table registration to enable after the corresponding warehouse table has been created and populated. The intended table is `marts.email_metric_targets`; it should contain targets for `email_subscribers`, `email_delivery_rate`, `email_open_rate`, and `email_click_rate`. Ratio targets require numerator and denominator values in addition to the displayed target value.

Current Analytics Engineering Jobs transformations live in [aej-dbt](https://github.com/kingfink/aej-dbt).

This is not a standalone project. The underlying warehouse models, data, credentials, and Steep workspace are not included.

## Rights

No open-source license is granted. All rights reserved.
