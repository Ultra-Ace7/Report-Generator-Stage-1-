# Sales REST API

Sales and task APIs are explicit adapters. Both use the public HTTPS transport,
port 443, DNS public-address validation and IP pinning, verified TLS, no redirects
or environment proxies, operation timeouts and a 20 MB decoded response limit.
Invalid JSON (including duplicate object keys), HTTP failures and incompatible
schemas fail without offline substitution. API responses are streamed to enforce
the limit before JSON parsing. There is no automatic pagination or authentication.

## Sales schema

A nonempty JSON array of objects is required:

```json
[{"order_id":"ORD001","order_date":"2026-10-05","customer":"ABC Pty Ltd","service":"Cloud Hosting","revenue":1500.00,"currency":"AUD"}]
```

All six fields are mandatory. The [sales field aliases](data-contract.md#external-csvxlsx-column-names)
apply independently to each object. Missing fields, ambiguous mappings, invalid
calendar dates, invalid money, non-AUD currency and duplicate IDs fail. Unrelated
fields follow the documented CSV rules. Money is parsed using Decimal. Dates
are actual transaction dates, never retrieval timestamps. API and local orders
are merged with duplicate checks, then filtered by the existing report dates.
The report records the API source with query parameters omitted. This identifies
the supplied source; it does not independently verify its accounting accuracy.

## UI

For API-only Sales Summary, disable Upload Files, enable Fetch from REST API,
select **Sales orders** under **API data type**, replace the default task URL
with your compatible public HTTPS sales endpoint, select matching dates and generate.
There is no bundled public sales endpoint: `/todos` is not a sales endpoint.
To combine inputs, keep Upload Files enabled and supply sales CSV/XLSX and/or
one metrics PDF. Sales API orders combine with local orders, not replace them.

**Task data** preserves the `/todos` schema: userId, id, title, completed.
Sales Summary can still combine local sales, PDF targets and this task overview.
Operations/KPI uses Task data only. The explicit Offline Sample Task Data mode
continues to work without network access when API fetching is disabled.

## CLI and reproducible mock

Production API-only command (replace the example URL with your own endpoint):

```bash
python cli.py --report sales_summary --start 2026-10-01 --end 2026-10-31 --sales-api-url https://example.com/orders --output output/sales_api.docx
```

Existing `--tasks live/offline/none` commands retain their meaning. The sales API
argument can be combined with `--sales`, `--metrics` and `--tasks`.
For a deterministic offline HTTP mock using the current fictional October sales CSV:

```bash
python -m scripts.demo_sales_api --report sales_summary --start 2026-10-01 --end 2026-10-31 --sales-api-url https://example.com/orders --output output/sales_api_mock.docx
```

This explicit test harness injects HTTPX MockTransport and makes no real network
request. It is not a live API demonstration or a production network bypass.
Expected revenue: AUD 7,390.00, five orders, one chart and no target comparison.
Existing output files are never overwritten; choose a new path for repeated runs.

## DummyJSON carts

The official https://dummyjson.com/docs/carts response is a cart envelope with
products, totals, discounts and user IDs. It lacks the required actual transaction
date and explicit AUD currency and does not establish completed sales. It is
therefore rejected, rather than relabelled as verified recognized revenue. No
cart snapshot report or invented date/currency conversion is included.
