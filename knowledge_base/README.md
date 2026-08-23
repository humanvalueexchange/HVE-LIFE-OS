# HVE Life OS — Knowledge Base

This directory is the **template** for `~/.hve/knowledge/`. It contains
placeholder structure files only (D5=A). Do NOT commit real personal
data or Hans's Customer Zero facts here.

## Deployment

After the first Mercury boot, copy these files into
`~/.hve/knowledge/` (owned by the `hve` service user, D6=B), then
edit them in place. The loader in `hve/kbase/loader.py` ingests
whatever is present at `~/.hve/knowledge/*.md` on each `hve init`
or `hve report generate`.
