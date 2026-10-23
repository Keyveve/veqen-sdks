"""Exercise the real Collector locally; no provider, Veqen account or credentials."""
import copy
import gzip
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
from urllib.request import Request, urlopen


def attrs(values):
    return [{"key": key, "value": {"intValue" if isinstance(value, int) else "stringValue": str(value)}}
            for key, value in values.items()]


def main(binary):
    received, ready = [], threading.Event()

    class Sink(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            assert self.path == "/v1/otlp/v1/traces"
            assert self.headers["Authorization"] == "Bearer test-placeholder"
            body = self.rfile.read(int(self.headers["Content-Length"]))
            if self.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            received.append(json.loads(body))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"{}")
            ready.set()

    sink = HTTPServer(("127.0.0.1", 0), Sink)
    threading.Thread(target=sink.serve_forever, daemon=True).start()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        receiver_port = sock.getsockname()[1]
    config = Path(__file__).with_name("collector.yaml").read_text()
    config = config.replace("127.0.0.1:4318", f"127.0.0.1:{receiver_port}")
    config = config.replace("https://veqen-app.com/v1/otlp", f"http://127.0.0.1:{sink.server_port}/v1/otlp")
    env = {**os.environ, "VEQEN_API_KEY": "test-placeholder"}
    with tempfile.TemporaryDirectory() as temporary:
        config_path = Path(temporary) / "collector.yaml"
        config_path.write_text(config)
        with open(Path(temporary) / "collector.log", "w+") as logs:
            process = subprocess.Popen([binary, "--config", str(config_path)], env=env, stdout=logs, stderr=logs,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            try:
                for _ in range(80):
                    assert process.poll() is None, "Collector exited before ready"
                    try:
                        with socket.create_connection(("127.0.0.1", receiver_port), timeout=0.2):
                            break
                    except OSError:
                        time.sleep(0.1)
                stamp = time.time_ns()
                span = {"traceId": "a" * 32, "spanId": "b" * 16, "name": "PRIVATE_SENTINEL",
                        "traceState": "secret=PRIVATE_SENTINEL", "startTimeUnixNano": str(stamp),
                        "endTimeUnixNano": str(stamp + 1000000),
                        "status": {"code": 2, "message": "PRIVATE_SENTINEL"},
                        "events": [{"name": "PRIVATE_SENTINEL", "timeUnixNano": str(stamp)}],
                        "attributes": attrs({"gen_ai.provider.name": "openai", "gen_ai.response.model": "gpt-4o",
                                             "gen_ai.usage.input_tokens": 100, "gen_ai.usage.output_tokens": 20,
                                             "gen_ai.usage.cache_read.input_tokens": 50,
                                             "openai.response.service_tier": "default",
                                             "gen_ai.input.messages": "PRIVATE_SENTINEL"})}
                second = copy.deepcopy(span)
                second["spanId"] = "e" * 16
                second["attributes"] += attrs({"veqen.feature": "span-override"})
                wrapper = {"traceId": "a" * 32, "spanId": "f" * 16, "name": "wrapper"}
                body = {"resourceSpans": [{"resource": {"attributes": attrs({"service.name": "example",
                        "veqen.feature": "resource-default", "veqen.customer": "customer-123",
                        "secret": "PRIVATE_SENTINEL"})}, "scopeSpans": [{"scope": {"name": "example",
                        "attributes": attrs({"secret": "PRIVATE_SENTINEL"})}, "spans": [span, second, wrapper]}]}]}
                request = Request(f"http://127.0.0.1:{receiver_port}/v1/traces", json.dumps(body).encode(),
                                  {"Content-Type": "application/json"})
                with urlopen(request, timeout=10) as response:
                    assert response.status == 200
                assert ready.wait(15), "No export received"
                assert "PRIVATE_SENTINEL" not in json.dumps(received)
                spans = [s for batch in received for r in batch["resourceSpans"] for scope in r["scopeSpans"] for s in scope["spans"]]
                assert len(spans) == 2, "Wrapper must not count as another call"
                for i, exported in enumerate(spans):
                    values = {a["key"]: next(iter(a["value"].values())) for a in exported["attributes"] if a.get("value")}
                    assert values["veqen.customer"] == "customer-123"
                    assert values["veqen.feature"] == ("resource-default" if i == 0 else "span-override")
                    assert int(values["gen_ai.usage.input_tokens"]) == 100
                    assert int(values["gen_ai.usage.cache_read.input_tokens"]) == 50
                    assert int(values["gen_ai.usage.output_tokens"]) == 20
                    assert values["gen_ai.openai.response.service_tier"] == "default"
                    assert not exported.get("events") and not exported.get("links")
                print("PASS: two calls, wrapper excluded, usage/cache/tier retained, attribution preserved, private fields removed")
            except Exception:
                logs.flush()
                logs.seek(0)
                print(logs.read(), file=sys.stderr)
                raise
            finally:
                process.terminate()
                process.wait(timeout=10)
                sink.shutdown()


if __name__ == "__main__":
    main(sys.argv[1])
