from __future__ import annotations

import gzip
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace as NS

import pytest

from veqen.client import client


@pytest.fixture(autouse=True)
def _fresh_client(monkeypatch):
    for name in ("VEQEN_API_KEY", "VEQEN_ENDPOINT", "VEQEN_ENVIRONMENT", "VEQEN_LEDGER_FILE"):
        monkeypatch.delenv(name, raising=False)
    client.configure(api_key="", ledger_file=None, environment=None)
    client.queue.clear()
    client.budgets.clear()
    client.blocked.clear()
    yield


@pytest.fixture
def ledger(tmp_path):
    """Point the SDK at a local ledger file; calling the fixture returns the recorded events."""
    from veqen import init

    path = tmp_path / "ledger.jsonl"
    init(ledger_file=str(path))
    return lambda: [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


@pytest.fixture
def server():
    """A local Veqen API that records event batches and serves budget status."""
    state = NS(events=[], blocked=[], headers=[])

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _reply(self, body: dict) -> None:
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            raw = self.rfile.read(int(self.headers["Content-Length"]))
            state.headers.append(dict(self.headers))
            state.events.extend(json.loads(gzip.decompress(raw))["events"])
            self._reply({"accepted": 1})

        def do_GET(self):
            self._reply({"blocked": state.blocked})

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    state.url = f"http://127.0.0.1:{httpd.server_address[1]}"
    yield state
    httpd.shutdown()


def fake_client(module: str, **resources):
    """An object whose type lives in ``module`` (how veqen.wrap detects the provider)."""
    cls = type("Client", (), {"__module__": module})
    instance = cls()
    for name, value in resources.items():
        setattr(instance, name, value)
    return instance
