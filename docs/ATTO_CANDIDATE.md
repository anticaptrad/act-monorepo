# AttoLang aggregate promotion hold

The two AttoLang source/contract candidates are **not** deployable or
publishable SDKs. `docs/atto-candidate-promotion.v1.json` records this
explicitly and the local test fails on accidental production promotion.

`packages/act-clients` and `packages/act-interfaces` remain independently
reviewed Git submodules. This draft does not move either gitlink or select a
candidate head for aggregate release. Advancing a gitlink requires approved
upstream PRs, executable compiler receipts, schema peer-authority parity and
a separate aggregate pin review.

Run `node --test scripts/test-atto-promotion.mjs`. The guard checks a
repository-local policy snapshot, not live upstream PR state or a compiler
artifact. It must not be used as a substitute for those checks.
