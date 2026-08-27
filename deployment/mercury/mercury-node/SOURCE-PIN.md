# Mercury Node Source Snapshot

> **Historical/experimental artifact.** Preserved as a Mercury source
> snapshot; it is not the active HVE Life OS deployment.

This directory is a vendored, source-only snapshot of the private
`humanvalueexchange/mercury-node` repository for HVE Life OS deployment
planning and review. The CLI file also contains the reviewed Mercury-host
runtime fixes listed below.

- Source repository: `https://github.com/humanvalueexchange/mercury-node`
- Source branch: `main`
- Pinned commit: `1dad9a1cb80c37a2a4fe5fc1fe96d8deb5a02296`
- Snapshot date: 2026-08-22

The nested Git metadata is intentionally excluded. Update this snapshot only
from a reviewed upstream commit and record the new commit here.

## Mercury-host runtime delta

The current `src/cli/mercury` includes the deployed Qwen3.8 local-model label
and fallback path, plus terminal-safe word wrapping for streamed responses.
These changes were applied on Mercury on 2026-08-22 and copied here so the
GitHub deployment reference matches the tested host behavior. The native
llama.cpp server binary is installed separately on Mercury and is not
vendored in this source snapshot.

## Integration boundary

Mercury remains an external alpha-node adapter. HVE Life OS may consume
sanitized, read-only operational evidence from Mercury, but must not import
wallet secrets, macaroons, raw invoices, payment requests, or fund-moving
commands.

The source contains privileged CLI operations such as payments, channel
management, rebalancing, and service control. Those operations are not
approved for HVE agent automation. The included source is therefore a review
and deployment reference, not permission to expose the complete Mercury CLI
through HVE.

The live Mercury node may use a newer locally built llama.cpp runtime and
model than the source snapshot's historical service template. The active
runtime contract belongs in the HVE deployment manifest and host runbook.
