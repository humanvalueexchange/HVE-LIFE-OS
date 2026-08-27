# HVE Life OS — Knowledge Base

This directory is the **template** for `~/.hve/knowledge/`. It contains
placeholder structure files only (D5=A). Do NOT commit real personal
data or Hans's Customer Zero facts here.

## Deployment

For the DGX Spark reference deployment, copy these files into the
directory-contained `HVE_KNOWLEDGE_DIR` (currently
`/home/hans/hve-life-os/data/knowledge`), then edit them in place. Generic
development defaults use `~/.hve/knowledge/`. The loader in
`hve/kbase/loader.py` ingests whatever is present at the configured
`HVE_KNOWLEDGE_DIR/*.md` on each `hve init` or `hve report generate`.
