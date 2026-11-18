# Testing and resilience checks

Run the complete suite from the project directory:

```bash
python -m pytest -q
```

The 19 November 2026 run passed 186 cases, including 9 new resilience cases.
There were 14 third-party deprecation warnings. This count is not a line or
branch coverage percentage. Earlier verification records retain their historical
177-case results.

`tests/test_resilience.py` covers:

- Unicode and long text through CSV to DOCX, including paths with spaces and
  Chinese characters, and exact cent arithmetic.
- 10,000 input rows with independent count and total checks.
- Five alternating report generations without accumulating rows or changing
  the source template.
- Exactly 20 MiB and one byte over the upload admission limit.
- Two independent AppTest sessions, including failure in one without changing
  the other's result. This is not a simultaneous browser load test.
- Three repeated UI generations without duplicate results or controls.
- Success, simulated API failure and explicit offline recovery in one session,
  ensuring an old download is not presented as a successful new result.

## Optional performance observation

```bash
python -m scripts.benchmark_report --rows 1000
```

The benchmark uses temporary synthetic CSV data, generates a real DOCX, checks
its row count and revenue, and prints JSON measurements. It does not modify
sample data or the template. A 1,000-row run on macOS / Python 3.9.6 took 4.377
seconds for generation, with 136.77 MiB process peak RSS. Input was 51,945 bytes;
DOCX was 102,583 bytes. These are single-run observations, not performance limits.
RSS includes imports and verification and is available on macOS/Linux; other
platforms report null. The benchmark is intentionally separate from normal tests
so machine speed does not create a brittle test assertion.

## Limits and further manual verification

- Text round-trip assertions do not verify visible glyphs or page layout. Check
  long and multilingual reports in the Word-compatible viewers being supported.
- AppTest session isolation does not prove concurrent-request scalability.
- One process peak-memory result does not prove absence of memory leaks.
- Windows has not been exercised in a real Windows environment.
- Existing API tests use controlled responses; previous live samples provide
  separate evidence of real connectivity, not current service availability.
