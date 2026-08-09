## Summary

<!-- What changed, and the request/problem this addresses. 1-3 bullets. -->

-

## Related plan/spec

<!-- Link to docs/superpowers/plans/... or specs/... if this came from a
     brainstorming/planning session. Otherwise: N/A — no written plan for
     this change. -->

## Verification

<!-- The three CI jobs in .github/workflows/tests.yml run both suites and the
     credential guard. Confirm the machine ran; do not transcribe its output.
     This box used to accept free text, so "ran the tests, green" satisfied it
     while having run 201 of 1,034 tests (findings F-61, F-80). -->

- [ ] `root-suite` green
- [ ] `app-suite` green
- [ ] `no-live-credentials` green

### Regression test for the defect this fixes

<!-- Required for any change closing an audit finding. Name the finding ID and
     the test you observed FAILING before the fix and passing after. Line
     coverage is diagnostic only and is not evidence (finding F-02). -->

- Finding: <!-- e.g. B-40 -->
- Test: <!-- e.g. pipeline-app/tests/test_discovery_engine.py::test_adapter_fault_exits_nonzero -->

### Manual walkthrough

<!-- Only for things no job can perform. -->
