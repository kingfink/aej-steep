# AEJ weekly review

This is a report build specification, not a published Steep report. On October 16, 2026, the Steep connector exposed the 18 AEJ modules and six entities, including Job, Organization, Page, and Email Campaign. Production joined-metric queries passed as recorded below. The connector currently exposes metric queries and entity metadata, but no report creation or entity-row query tools; report configuration and row-level drill-downs remain unverified.

## Questions

- Which jobs attracted attention and outbound apply clicks?
- Which acquisition channels contributed captured engagement?
- How did the latest newsletter perform?
- Is a change in results accompanied by a change in measurement coverage?

## Periods and filters

Set the main report to the last completed calendar week and compare with the preceding completed week. Use UTC consistently with the warehouse contracts and confirm the workspace week boundary before publishing. For a current-month view, use a matching to-date comparison. A changing date filter does not confirm that upstream data is fresh.

Keep the provisional audience-growth block on its own rolling 28 completed days with the preceding 28 days for comparison. It must ignore the weekly report period. Label its session-start attribution as provisional; this report does not approve the pending session-start versus activity-window decision.

Avoid a global channel or campaign filter: these dimensions are not shared by every metric. Apply filters to the relevant blocks. Use the same channel colors throughout the report, with an accessible theme such as Okabe-Ito.

## Blocks

| Block | Metrics by stable identifier | Layout and interpretation |
| --- | --- | --- |
| Web activity | `page_views`, `apply_clicks`, `apply_click_rate` | Weekly values with prior-week comparisons. Clicks indicate outbound intent, not completed applications. The rate is clicks per page view, not a session conversion rate. |
| Job performance | `page_views`, `apply_clicks`, `apply_click_rate`, `job_link_clicks`, `job_link_clickers` | Expandable rows: `dim_jobs.organization_slug` → `dim_jobs.job_slug`. Show `title` as a display breakdown if useful. Sort by apply clicks descending, retaining page views as exposure context. Do not interpret newsletter clicks as deduplicated site visitors. |
| Acquisition | `page_views`, `apply_clicks` | Break down each metric by `dim_web_sessions.channel`; show null separately from `direct` and `unknown`. `internal` is a session rollover, not an external acquisition channel. These two metrics support channel; `apply_click_rate` currently does not expose it. |
| Provisional audience outcome | `engaged_job_seeker_sessions`, `engaged_session_apply_rate` | Rolling 28-day values plus a channel breakdown. Count captured sessions, not people. Preserve the landing-only exclusions and provisional time basis in the block text. |
| Newsletter outcomes | `email_subscriber_messages_delivered`, `email_open_rate`, `email_click_rate` | Weekly table by `dim_email_messages.subject` and provider `source`. Date attribution is message send time. Privacy-proxied and bot-like activity remains included. |
| Newsletter job attention | `job_link_clicks`, `job_link_clickers` | Table by campaign subject and campaign date from `dim_email_campaigns`, with `is_test = false` and an explicit selection of newsletter campaigns. Excluding tests alone still includes transactional campaigns such as resume reviews. These campaign dimensions are available on the link metrics; they are not currently exposed on the message-outcome rates. |
| Measurement coverage | `page_view_attribution_coverage`, `form_submission_attribution_coverage` | Weekly values with prior-week comparisons. Keep this visible beside acquisition findings. Use form coverage only for periods from August 2026 onward. |

Keep the newsletter and site metrics separate where they measure different populations. In particular, do not sum visitor or subscriber distinct counts across rows. Let Steep recompute totals and ratios. Apply Top X deliberately: confirm which metric controls ranking and whether totals include values outside the visible rows.

The existing Job and Email Campaign entities are candidates for cell drill-downs after entity sync and access are verified. Keep subscriber drill-downs PII-safe.

## Optional blocks

- **Search:** Use `site_search_clicks` and `site_search_impressions` for site totals. Use the URL-level `search_clicks` and `search_impressions` for job/page analysis. Never add the two sources. Search Console arrives two to three days late, so verify availability before comparing completed weeks, or give this block its own complete comparison window.
- **Subscribers:** `email_subscribers` is a daily active-at-any-point count, averaged over coarser periods. Label a weekly card as average daily subscribers, not subscribers at week end. Use a single complete date for a daily value.
- **Jobs and salary:** Snapshot metrics use the latest date separately for each breakdown group. Keep their date settings independent of the weekly flow metrics, show the as-of date and `listed_jobs_with_salary`, and preserve all salary caveats. Do not publish pay summaries with fewer than 10 observations. Historical attributes reflect current job attributes.
- **Targets:** Leave out until agreed targets exist in a populated warehouse table. `targets.yml.example` is documentation, not an active registration.

## Verification before publishing

1. Confirm the connection is the AEJ workspace and check the latest upstream data dates.
2. Query affected metrics and at least one joined dimension through the AEJ Steep MCP; test the job and campaign breakdowns above, including any null groups.
3. Check the report's week boundaries, comparison dates, independent block periods, filters, Top X behavior, and ratio/distinct-count totals.
4. Verify entity discovery and a cell drill-down without exposing subscriber email addresses.
5. Record the report URL and any remaining measurement decisions here after creation.

## Production query checks, October 16, 2026

The AEJ Steep MCP successfully ran these queries with `hasMore: false` in every response:

- `page_views` by both organization slug and job slug, October 5–11. This verifies the job join and multiple breakdowns. The response includes a null-job group; retain or explicitly separate it from identified jobs rather than treating it as a job posting.
- `engaged_job_seeker_sessions` by acquisition channel, September 18–October 15, covering 28 completed days. This verifies the session dimension join, not approval of the provisional metric or its attribution basis.
- `job_link_clicks` by campaign subject, October 5–11, filtered to `is_test = false`. This verifies the two-step campaign join and filter. The response includes a transactional resume-review campaign, so a newsletter-only block also needs an explicit newsletter campaign selection.

These checks ran against the current production model. They do not establish warehouse freshness or verify the description edits in PR #18, which have not been merged or synced. A workspace-aware sync preview still requires the AEJ datasource identifier and API credential. No report was created.

## Release references

- [Completed-period and to-date comparisons](https://steep.app/changelog/favorites-and-sidebar)
- [Tables, hierarchies, comparisons, and totals](https://steep.app/changelog/tables-reimagined)
- [Pivot/cohort drill-downs and Markdown descriptions](https://steep.app/changelog/drill-down-pivot-cohort)
- [Report access through API/MCP](https://steep.app/changelog/api-mcp-improvements)
