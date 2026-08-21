# Mercury Alpha Deployment

This profile runs HVE Life OS on the minimum portable target: an ARM64
Raspberry Pi using local `llama.cpp` inference and a quantized Qwen2.5 3B
Instruct model.

## Runtime contract

```text
Hermes source: /home/hermes/.hermes/hermes-agent
Hermes config: /home/hermes/.hermes/config.yaml
Model:         /opt/mercury/models/qwen2.5-3b-instruct-q4_k_m.gguf
API endpoint:  http://127.0.0.1:8089/v1
Context:       8192 tokens
```

The endpoint must remain loopback-only unless an authenticated and explicitly
approved remote access design is added.

## Installation sequence

1. Install a pinned Nous Hermes release or commit into the Hermes runtime
   location.
2. Install `llama.cpp` and place the verified GGUF model at the manifest path.
3. Apply `patches/hermes-context-floor.patch` if the selected upstream revision
   still enforces a 64K minimum.
4. Install this directory's configuration overlay without copying secrets.
5. Set `HERMES_MINIMUM_CONTEXT_LENGTH=8192` in the service environment.
6. Start the model backend and Hermes service.
7. Run the smoke test and record the runtime evidence.

The installer must verify the upstream commit, model checksum, service
configuration, endpoint binding, and context length before declaring success.

## Rollback

Keep the previous Hermes revision, configuration, and service environment
available until the new build passes its Mercury health check. Rollback must
restore the prior revision and restart the affected services; it must not
delete user data or SQLite databases.

## Future platform adapters

Ubuntu on Windows and macOS should reuse the same model/API and HVE
configuration contracts. Only the installer, process supervisor, filesystem
paths, and hardware-acceleration adapter should vary by platform.
