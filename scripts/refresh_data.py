"""Refresh the public CC0 upstream list; reject empty or malformed downloads."""
import json
from pathlib import Path
from urllib.request import Request, urlopen
ROOT = Path(__file__).resolve().parents[1]
HEAD = "https://api.github.com/repos/disposable-email-domains/disposable-email-domains/commits/main"
with urlopen(Request(HEAD, headers={"User-Agent": "veqen-public-data"}), timeout=60) as r:
    revision = json.load(r)["sha"]
base = f"https://raw.githubusercontent.com/disposable-email-domains/disposable-email-domains/{revision}"
with urlopen(base + "/disposable_email_blocklist.conf", timeout=60) as r:
    text = r.read().decode("utf-8")
values = sorted(set(line.strip().lower() for line in text.splitlines() if line.strip() and not line.startswith("#")))
assert len(values) >= 1000, "Unexpectedly small list; preserving the last copy"
assert all("." in value and not any(c.isspace() for c in value) for value in values)
data = ROOT / "data"
data.mkdir(exist_ok=True)
(data / "disposable-email-domains.txt").write_text("\n".join(values) + "\n", encoding="utf-8")
(data / "source.json").write_text(json.dumps({"repository": "https://github.com/disposable-email-domains/disposable-email-domains", "revision": revision, "license": "CC0-1.0", "domains": len(values)}, indent=2) + "\n", encoding="utf-8")
print(f"Refreshed {len(values)} domains at {revision}")
