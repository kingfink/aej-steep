# aej-steep

Steep semantic-layer definitions created for [Analytics Engineering Jobs](https://www.analyticsengineeringjobs.com/).

This repository is published as a small reference and showcase of defining metrics in code with [Steep](https://steep.app/). It is maintained for my own use; issues and pull requests are not accepted.

## Model

[`fct_events.yml`](fct_events.yml) defines a Steep module and event-count metric for GA4 events. It depends on legacy SQLMesh models and is scheduled for deprecation, but is retained here as an example of the original semantic-layer implementation.

Current Analytics Engineering Jobs transformations live in [aej-dbt](https://github.com/kingfink/aej-dbt).

This is not a standalone project. The underlying warehouse models, data, credentials, and Steep workspace are not included.

## Rights

No open-source license is granted. All rights reserved.
