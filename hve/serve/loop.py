"""Loopback HTTP service entry point (started by systemd).

Runs on 127.0.0.1 by default; the :class:`hve.config.HveConfig`
constructor *refuses* to start if the host is anything but a loopback
address, so a misconfigured ``HVE_HTTP_HOST`` will surface at startup.
"""

from __future__ import annotations

import sys

from ..config import load
from .health import serve


def main() -> int:
    cfg = load()
    server = serve(cfg, block=True)
    try:
        print(
            f"hve serve: listening on http://{cfg.http_host}:{cfg.http_port} "
            f"(loopback-only; endpoints: /healthz /status.json /report)"
        )
        # Block forever; systemd sends SIGTERM on stop.
        import signal
        import threading
        stop = threading.Event()
        def _sig(sig, frame):  # noqa: ANN001
            print("hve serve: shutting down", flush=True)
            stop.set()
            server.shutdown()
        signal.signal(signal.SIGTERM, _sig)
        signal.signal(signal.SIGINT, _sig)
        while not stop.is_set():
            stop.wait(1)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
