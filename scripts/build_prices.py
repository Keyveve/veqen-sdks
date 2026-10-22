"""Build Veqen's price book from LiteLLM's MIT-licensed price file plus Veqen's verified rules.

    python scripts/build_prices.py [path-or-url-to-model_prices_and_context_window.json]

Writes the same price book into both SDKs (the server reads the Python SDK's copy) and appends any price
changes to the Python SDK's price_history.json. Token rates are USD per million tokens; unit rates (per
image, per second of audio or video, per character, per query, per page) are USD per unit.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LITELLM_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
PY_DATA = ROOT / "python" / "veqen" / "data"
PY_BOOK = PY_DATA / "prices.json"
JS_BOOK = ROOT / "js" / "src" / "prices.js"  # a module, so every bundler can import it
HISTORY = PY_DATA / "price_history.json"
SCHEMA = 2

# input_cost_per_token[_above_200k_tokens][_batches] and friends -> (field, tier threshold, mode)
_FIELD = re.compile(
    r"^(input_cost_per_token|output_cost_per_token|cache_read_input_token_cost|cache_creation_input_token_cost"
    r"|input_cost_per_audio_token|output_cost_per_audio_token)"
    r"(_above_1hr)?(?:_above_(\d+)k_tokens)?(?:_(batches|priority|flex))?$"
)
_NAMES = {
    "input_cost_per_token": "in",
    "output_cost_per_token": "out",
    "cache_read_input_token_cost": "cr",
    "cache_creation_input_token_cost": "cw",
    "input_cost_per_audio_token": "ain",
    "output_cost_per_audio_token": "aout",
}
_MODES = {None: "standard", "batches": "batch", "priority": "priority", "flex": "flex"}
_KINDS = {
    "chat": "text", "responses": "text", "completion": "text", "embedding": "embedding", "image_generation": "image",
    "image_edit": "image", "video_generation": "video", "audio_speech": "speech", "audio_transcription": "transcription",
    "realtime": "realtime", "rerank": "rerank", "ocr": "ocr",
}
_SIZE = re.compile(r"^(\d+)-x-(\d+)$")
_VARIANT_PART = re.compile(r"^(\d+-x-\d+|\d+-steps|max-steps|low|medium|high|standard|hd|auto)$")
_REGION_PART = re.compile(r"^[a-z]{2}(-gov)?-[a-z]+-\d$")  # region-specific price lists duplicate the default ones
_PSEUDO = re.compile(r"^(together-ai|fireworks-ai)-")  # LiteLLM's model-size price buckets, not models
_LABS_ON_BEDROCK = re.compile(r"^(?:[a-z]{2,7}\.)?(anthropic|openai|mistral|deepseek)\.")  # priced as the lab's models
_BEDROCK_PROFILE = re.compile(r"^(?:us|eu|apac|jp|au|ca|global|us-gov)\.")
_RESOLUTIONS = ("480p", "720p", "1080p", "4k")
_MAX_TOKEN_RATE = 1000.0  # USD per 1M: nothing real costs more, so a higher rate is a per-1K price filed as per-token


def _num(value: float) -> float:
    return float(f"{value:.6g}")


def _rates(entry: dict) -> dict[str, dict[str, float]]:
    """{"standard": {...}, "batch": {...}, "standard>200000": {...}} with per-1M token rates."""
    rates: dict[str, dict[str, float]] = {}
    for key, value in entry.items():
        match = _FIELD.match(key)
        if not match or not isinstance(value, (int, float)):
            continue
        base, one_hour, tier, mode = match.groups()
        field = "cw1h" if one_hour else _NAMES[base]
        bucket = _MODES[mode] + (f">{int(tier) * 1000}" if tier else "")
        rates.setdefault(bucket, {})[field] = round(value * 1_000_000, 6)
    standard = rates.setdefault("standard", {})
    if "cr" not in standard and isinstance(entry.get("input_cost_per_token_cache_hit"), float):
        standard["cr"] = round(entry["input_cost_per_token_cache_hit"] * 1_000_000, 6)
    if "out" not in standard and isinstance(entry.get("output_cost_per_image_token"), float):  # gpt-image bills image tokens
        standard["out"] = round(entry["output_cost_per_image_token"] * 1_000_000, 6)
    if not standard:
        del rates["standard"]
    return rates


def _unit(entry: dict, kind: str, size: tuple[int, int] | None) -> tuple[str | None, float | None, dict[str, float]]:
    """The model's billing unit, its per-unit rate, and any per-resolution rates."""
    if kind == "image":
        per = entry.get("output_cost_per_image") or entry.get("input_cost_per_image")
        pixel = (entry.get("input_cost_per_pixel") or 0) + (entry.get("output_cost_per_pixel") or 0)
        if per is None and pixel and size:
            per = size[0] * size[1] * pixel
        return "image", per, {}
    if kind == "video":
        per = entry.get("output_cost_per_second") or entry.get("output_cost_per_video_per_second") or entry.get("cost_per_second")
        return "second", per, {r: entry[f"output_cost_per_second_{r}"] for r in _RESOLUTIONS if entry.get(f"output_cost_per_second_{r}")}
    if kind in ("transcription", "realtime") and entry.get("input_cost_per_second") and not entry.get("input_cost_per_token"):
        return "second", entry["input_cost_per_second"], {}
    if kind == "speech":
        if entry.get("input_cost_per_character"):
            return "character", entry["input_cost_per_character"], {}
        if entry.get("output_cost_per_second") and not entry.get("output_cost_per_audio_token"):
            return "second", entry["output_cost_per_second"], {}
    if kind == "rerank" and entry.get("input_cost_per_query"):
        return "query", entry["input_cost_per_query"], {}
    if kind == "ocr" and entry.get("ocr_cost_per_page"):
        return "page", entry["ocr_cost_per_page"], {}
    return None, None, {}


def _split_key(key: str, prefixes: set[str]) -> tuple[str, str, tuple[int, int] | None]:
    """(model id, variant, image size) from keys such as "hd/1024-x-1792/dall-e-3" or "fal_ai/fal-ai/flux/dev"."""
    variant: list[str] = []
    model: list[str] = []
    size = None
    for part in key.split("/"):
        if not model and part in prefixes:
            continue
        if not model and _VARIANT_PART.match(part):
            if found := _SIZE.match(part):
                size = (int(found.group(1)), int(found.group(2)))
            variant.append(part.replace("-x-", "x"))
            continue
        model.append(part)
    return "/".join(model), "/".join(variant), size


def _default_variant(variants: dict[str, float]) -> float:
    """What a call that names no size or quality costs: 1024x1024 at standard quality, else the cheapest."""
    for wanted in ("standard/1024x1024", "medium/1024x1024", "1024x1024", "auto/1024x1024"):
        if wanted in variants:
            return variants[wanted]
    return min(variants.values())


def build(source: dict, rules: dict, retirements: dict) -> dict:
    retire = {
        (r["provider"], model_id): (r["date"], r.get("replacement"))
        for r in retirements["models"]
        for model_id in r["ids"]
    }
    owner = {lp: provider for provider, meta in rules["providers"].items() for lp in meta["litellm"]}
    models: dict[str, dict] = {}
    variants: dict[str, dict[str, float]] = {}
    for key, entry in source.items():
        if not isinstance(entry, dict) or (provider := owner.get(entry.get("litellm_provider"))) is None:
            continue
        kind = _KINDS.get(entry.get("mode"))
        if kind is None or _PSEUDO.match(key) or any(_REGION_PART.match(part) for part in key.split("/")):
            continue
        model, variant, size = _split_key(key, {entry["litellm_provider"], provider, "bedrock"})
        if provider == "bedrock":
            if _LABS_ON_BEDROCK.match(model):
                continue
            model = _BEDROCK_PROFILE.sub("", model)
        if not model or model.startswith("ft:"):
            continue
        name = f"{provider}/{model}"
        if name in rules["exclude"]:  # add-ons and other entries that aren't models
            continue
        rates = _rates(entry)
        if any(value > _MAX_TOKEN_RATE for bucket in rates.values() for value in bucket.values()):
            continue
        unit, per_unit, resolutions = _unit(entry, kind, size)
        if per_unit is not None and variant:
            variants.setdefault(name, {})[variant] = _num(per_unit)
        elif per_unit is not None:
            rates.setdefault("standard", {})["unit"] = _num(per_unit)
        rates.update({f"v:{r}": {"unit": _num(value)} for r, value in resolutions.items()})
        current = models.get(name)
        if (not rates and per_unit is None) or (current is not None and (variant or len(current["rates"]) >= len(rates))):
            continue
        item: dict = {"rates": rates}
        if kind != "text":
            item["kind"] = kind
        if unit and per_unit is not None:
            item["unit"] = unit
        if kind == "text" and entry.get("max_input_tokens"):
            item["context"] = entry["max_input_tokens"]
        date, replacement = retire.get((provider, model), (entry.get("deprecation_date"), None))
        if date:
            item["retires"] = date
        if replacement:
            item["replacement"] = replacement
        models[name] = {**item, **rules.get("fixes", {}).get(name, {})}
    for name, found in variants.items():
        item = models.setdefault(name, {"rates": {}, "kind": "image"})
        item["rates"].update({f"v:{v}": {"unit": rate} for v, rate in sorted(found.items())})
        item["rates"].setdefault("standard", {}).setdefault("unit", _default_variant(found))
        item.setdefault("unit", "image")
    return {
        "version": datetime.now(UTC).strftime("%Y-%m-%d"),
        "schema": SCHEMA,
        "source": "LiteLLM model_prices_and_context_window.json (MIT) with Veqen's verified rules",
        "providers": {p: {"name": m["name"], "group": m["group"], "pricing_url": m["pricing_url"]} for p, m in rules["providers"].items()},
        "aliases": rules["aliases"],
        "hosts": rules["hosts"],
        "residency": rules["residency"],
        "api_retirements": retirements["apis"],
        "models": dict(sorted(models.items())),
    }


def _changes(old: dict, new: dict, version: str) -> list[dict]:
    """Every change that affects a price: standard rates are listed one by one for the changelog; any other
    difference (batch, tiers, cache writes, context, retirement) is recorded as "updated"."""
    if old.get("schema", 1) < SCHEMA:
        return []  # a new book format starts a new baseline rather than listing every model as "added"
    changes = []
    old_models, new_models = old.get("models", {}), new["models"]
    for name, item in new_models.items():
        before = old_models.get(name)
        if before is None:
            changes.append({"date": version, "model": name, "change": "added"})
            continue
        listed = False
        for field in ("in", "out", "cr", "unit"):
            a, b = before["rates"].get("standard", {}).get(field), item["rates"].get("standard", {}).get(field)
            if a != b:
                listed = True
                changes.append({"date": version, "model": name, "field": field, "old": a, "new": b})
        if not listed and before != item:
            changes.append({"date": version, "model": name, "change": "updated"})
    changes += [{"date": version, "model": n, "change": "removed"} for n in old_models if n not in new_models]
    return changes


def dump(book: dict) -> str:
    """One model per line keeps price changes readable in diffs."""
    head = {k: v for k, v in book.items() if k != "models"}
    lines = [json.dumps(head, separators=(",", ":"), ensure_ascii=False)[:-1] + ',"models":{']
    lines.append(",\n".join(f"{json.dumps(k)}:{json.dumps(v, separators=(',', ':'))}" for k, v in book["models"].items()))
    return "\n".join(lines) + "}}\n"


def main(argv: list[str]) -> None:
    location = argv[1] if len(argv) > 1 else LITELLM_URL
    if location.startswith("http"):
        with urllib.request.urlopen(location, timeout=60) as response:  # noqa: S310 - fixed public URL
            source = json.load(response)
    else:
        source = json.loads(Path(location).read_text(encoding="utf-8"))
    rules = json.loads((ROOT / "pricebook" / "rules.json").read_text(encoding="utf-8"))
    retirements = json.loads((ROOT / "pricebook" / "retirements.json").read_text(encoding="utf-8"))
    book = build(source, rules, retirements)
    previous = json.loads(PY_BOOK.read_text(encoding="utf-8")) if PY_BOOK.exists() else {}
    floor = max(100, int(len(previous.get("models", {})) * 0.9))
    if len(book["models"]) < floor:
        raise SystemExit(f"Only {len(book['models'])} models priced (expected {floor}+); refusing to publish a broken price book")
    changes = _changes(previous, book, book["version"]) if previous else []
    if previous.get("schema", 1) == SCHEMA and not changes:
        book["version"] = previous["version"]  # nothing changed: keep the published version
    PY_BOOK.write_text(dump(book), encoding="utf-8", newline="\n")
    JS_BOOK.write_text(f"export default {dump(book).rstrip()};\n", encoding="utf-8", newline="\n")
    history = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else []
    HISTORY.write_text(json.dumps(history + changes, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(book['models'])} models, version {book['version']}, {len(changes)} changes")


if __name__ == "__main__":
    main(sys.argv)
