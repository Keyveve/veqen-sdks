"""Build data-only packages from the reviewed SDK snapshot. No network access."""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "python" / "veqen" / "data" / "prices.json"
book = json.loads(SOURCE.read_text(encoding="utf-8"))
assert book["schema"] == 2 and len(book["models"]) > 100
version = ".".join(str(int(part)) for part in book["version"].split("-"))
python = ROOT / "pricebook-packages" / "python"
javascript = ROOT / "pricebook-packages" / "js"
package = python / "veqen_pricebook"
package.mkdir(parents=True, exist_ok=True)
javascript.mkdir(parents=True, exist_ok=True)
for folder in (python, javascript):
    shutil.copyfile(ROOT / "python" / "LICENSE", folder / "LICENSE")
    shutil.copyfile(ROOT / "python" / "THIRD_PARTY_NOTICES", folder / "THIRD_PARTY_NOTICES")
    shutil.copyfile(ROOT / "pricebook-packages" / "README.md", folder / "README.md")
shutil.copyfile(SOURCE, package / "prices.json")
shutil.copyfile(SOURCE, javascript / "prices.json")
(javascript / "index.js").write_text("export default " + json.dumps(book, separators=(",", ":")) + ";\n", encoding="utf-8")
metadata = {
    "name": "@veqen/pricebook", "version": version, "description": "Dated AI model prices, cache rates and billing rules. Offline, with no tracking dependencies.",
    "type": "module", "main": "./index.js", "exports": {".": "./index.js", "./prices.json": "./prices.json"},
    "files": ["index.js", "prices.json", "README.md", "LICENSE", "THIRD_PARTY_NOTICES"],
    "license": "MIT", "homepage": "https://veqen-app.com/docs/price-book",
    "repository": {"type": "git", "url": "git+https://github.com/Keyveve/veqen-sdks.git", "directory": "pricebook-packages/js"},
    "keywords": ["ai", "llm", "pricing", "cost", "openai", "anthropic", "pricebook"],
    "publishConfig": {"access": "public"}, "scripts": {"test": "node --test test.mjs"},
}
(javascript / "package.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
template = (python / "pyproject.template.toml").read_text(encoding="utf-8")
(python / "pyproject.toml").write_text(template.replace("VERSION_PLACEHOLDER", version), encoding="utf-8")
print(f"Prepared price-book packages {version}, {len(book['models'])} models, schema {book['schema']}")
