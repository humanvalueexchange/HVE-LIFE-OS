# PARKED / EXPERIMENTAL — HVE Life OS M2 Mercury Backlog

> This is a preserved planning record for optional Mercury integration. It
> does not describe the active Alpha v1 target, which is DGX Spark.

## M2-01: Integrate Mercury Node as the Alpha Infrastructure Adapter

**Status:** Planned  
**Source reviewed:** `humanvalueexchange/mercury-node`  
**Reviewed commit:** `1dad9a1cb80c37a2a4fe5fc1fe96d8deb5a02296`  
**Local clone:** `/home/hans/humanvalueexchange/workspaces/mercury-node`

### Objective

Use Mercury Node as an optional deployment adapter and runtime evidence source
for HVE Life OS on the Raspberry Pi alpha. HVE Life OS must remain useful
without Mercury's Bitcoin and Lightning features, and Mercury must continue to
operate safely if the HVE application or AI layer is unavailable.

### What Mercury Node currently does

- Provides the `mercury` terminal CLI for node status, sync, peers, channels,
  invoices, payments, invoices, backups, logs, fees, routing, and health.
- Wraps `bitcoin-cli` and `lncli` for operational queries and selected payment
  or channel actions.
- Provides an interactive shell and AI-assisted `mercury ask` workflow.
- Runs a FastAPI agent service with loopback API endpoints for status, channels,
  invoices, sync, peers, backups, and Magma liquidity intelligence.
- Uses a local LLM endpoint for AI responses and injects live node state into
  prompts.
- Includes planned or partially implemented agent-mesh concepts around MCP,
  peer discovery, and Lightning payment-gated queries.
- Uses systemd-managed Bitcoin, LND, Mercury agent, and local LLM services.

### M2 implementation scope

1. Define a read-only HVE adapter for Mercury health, node state, channel
   state, payment summaries, and backup freshness.
2. Map Mercury evidence into HVE Life OS facts without copying secrets,
   wallet material, macaroons, invoices, payment requests, or personal data.
3. Add model-provider capability detection so HVE can distinguish ordinary
   completion from reliable structured tool calling.
4. Integrate the Mercury local LLM endpoint only through the existing HVE
   deployment contract; do not make HVE dependent on Mercury's CLI internals.
5. Add a deterministic health report showing whether Mercury, LND, Bitcoin
   Core, the model endpoint, and HVE are independently healthy.
6. Document installation by pinned commit and verified model checksum.
7. Add failure and rollback behavior proving that HVE remains operational when
   Mercury, LND, or the local model is stopped.

### Safety constraints

- Mercury remains an optional adapter, not HVE Life OS's source of truth.
- No HVE service may gain wallet-write access.
- No automated payment, channel, rebalance, treasury, or account action.
- Any action that can move funds must remain outside the HVE automation path and
  require explicit human confirmation.
- Keep Mercury and HVE service users, files, databases, and systemd units
  separated.
- Do not import Mercury's broad CLI into the HVE application without first
  extracting and reviewing the required read-only interfaces.
- Keep network exposure loopback-only unless a separately approved interface
  and authentication design exists.
- Preserve the ability to remove Mercury without corrupting HVE data.

### Review findings to resolve before implementation

- The deployed CLI is a large single-file executable rather than a packaged
  source distribution; establish a pinned source/build contract.
- The CLI contains direct payment, channel, rebalance, deposit, and send
  commands; these must not be exposed through HVE's agent path.
- The reviewed Mercury Node CLI (not HVE Life OS) defaults to a remote Ollama
  URL while also using a local `llama.cpp` endpoint; provider selection and
  data routing need explicit configuration. This remains outside the active
  HVE runtime, where Ollama is prohibited.
- The FastAPI service enables permissive CORS and binds to `0.0.0.0` in the
  source unit; validate that the alpha deployment is loopback-only.
- The repository documentation contains stale version, roadmap, domain, and
  hardware claims that must not be copied into canonical HVE documentation
  without runtime verification.
- The current Mercury model service is configured for Qwen2.5-3B at 8K
  context; model replacement and Hermes compatibility require a separate,
  reversible validation path.

### Acceptance criteria

- HVE can read a sanitized Mercury health snapshot through a documented,
  read-only adapter.
- HVE facts and reports contain no wallet secrets, macaroons, raw invoices, or
  payment requests.
- Stopping Mercury does not stop HVE Life OS or make the SQLite facts store
  unavailable.
- The adapter rejects or ignores fund-moving capabilities.
- The Mercury model endpoint's context and tool-call behavior are recorded
  from live tests, not inferred from model names.
- The integration is covered by focused tests and a repeatable Mercury
  deployment/rollback procedure.
