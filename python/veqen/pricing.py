"""The price book: exact USD cost for any priced inference call. Text, embedding and realtime models are
priced per token (with caching, batch, service tiers, long-context tiers and residency multipliers); image,
video, speech, transcription, rerank and OCR models per unit (image, second, character, query, page), with
size, quality and resolution variants. Works offline from the bundled prices.json."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

_DATE = re.compile(r"-(\d{8}|\d{4}-\d{2}-\d{2}|\d{3})$")
# Bedrock ids such as "us.anthropic.claude-sonnet-4-5-20250929-v1:0" are the labs' models
_BEDROCK_LAB = re.compile(r"^(?:[a-z]{2,7}\.)?(anthropic|openai|mistral|deepseek)\.(.+?)(?:-v\d+(?::\d+)?)?$")
_BEDROCK_PROFILE = re.compile(r"^(?:us|eu|apac|jp|au|ca|global|us-gov)\.(?=[a-z0-9-]+\.)")
_TIERS = {"batch": "batch", "priority": "priority", "flex": "flex"}


@dataclass(frozen=True)
class Usage:
    """What a call used, as billed. ``input_tokens`` excludes cache reads and writes; ``output_tokens``
    includes reasoning tokens. Cache writes default to the 5-minute TTL. ``units`` counts whatever a
    non-token model bills by: images, seconds of audio or video, characters, queries or pages."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cache_write_1h_tokens: int = 0
    audio_input_tokens: int = 0
    audio_output_tokens: int = 0
    units: float = 0

    @property
    def prompt_tokens(self) -> int:
        return (self.input_tokens + self.cache_read_tokens + self.cache_write_tokens + self.cache_write_1h_tokens
                + self.audio_input_tokens)

    @property
    def tokens(self) -> int:
        return self.prompt_tokens + self.output_tokens + self.audio_output_tokens


@dataclass(frozen=True)
class Price:
    key: str
    provider: str
    model: str
    rates: dict
    kind: str = "text"  # text, embedding, realtime, image, video, speech, transcription, rerank, ocr
    unit: str | None = None  # image, second, character, query or page, for models billed per unit
    context: int | None = None
    retires: str | None = None
    replacement: str | None = None

    def rate(self, field: str, mode: str = "standard", tier: int | None = None) -> float | None:
        """Per-million token rate for one field, deriving missing batch/priority/flex rates from the
        standard rate and the mode's input discount."""
        exact = self.rates.get(f"{mode}>{tier}" if tier else mode, {}).get(field)
        if exact is not None:
            return exact
        base = self.rates.get(f"standard>{tier}" if tier else "standard", {}).get(field)
        if base is None:
            return self.rate(field, mode) if tier else None
        mode_in, std_in = self.rates.get(mode, {}).get("in"), self.rates.get("standard", {}).get("in")
        return base * mode_in / std_in if mode != "standard" and mode_in and std_in else base

    def unit_rate(self, variant: str | None = None) -> float | None:
        """USD per unit for a variant (an image size and quality such as "hd/1024x1792", or a video resolution
        such as "1080p"), falling back to the same size at any quality, then the standard rate."""
        if variant:
            variant = variant.lower().replace("-x-", "x")
            if (exact := self.rates.get(f"v:{variant}", {}).get("unit")) is not None:
                return exact
            size = variant.rsplit("/", 1)[-1]
            same_size = sorted(k for k in self.rates if k.startswith("v:") and k.endswith(f"/{size}"))
            if same_size:
                return self.rates[same_size[0]]["unit"]
        return self.rates.get("standard", {}).get("unit")

    def tier_for(self, prompt_tokens: int) -> int | None:
        thresholds = {int(k.split(">")[1]) for k in self.rates if ">" in k}
        return max((t for t in thresholds if prompt_tokens > t), default=None)

    def cost(
        self,
        usage: Usage,
        *,
        batch: bool = False,
        service_tier: str | None = None,
        residency: str | None = None,
        variant: str | None = None,
        multipliers: dict | None = None,
    ) -> float | None:
        """USD cost, or None when the call used something this model has no rate for."""
        mode = "batch" if batch else _TIERS.get((service_tier or "").lower(), "standard")
        tier = self.tier_for(usage.prompt_tokens)
        rin, rout = self.rate("in", mode, tier), self.rate("out", mode, tier)
        total, tokens_priced = 0.0, False
        if usage.tokens and (rin is not None or rout is not None):
            rcr, rcw = self.rate("cr", mode, tier), self.rate("cw", mode, tier)
            rcw1h = self.rate("cw1h", mode, tier)
            rain, raout = self.rate("ain", mode, tier), self.rate("aout", mode, tier)
            terms = (
                (usage.input_tokens, rin),
                (usage.output_tokens, rout),
                (usage.cache_read_tokens, rin if rcr is None else rcr),
                (usage.cache_write_tokens, rin if rcw is None else rcw),
                (usage.cache_write_1h_tokens, rcw1h if rcw1h is not None else rin if rcw is None else rcw),
                (usage.audio_input_tokens, rin if rain is None else rain),
                (usage.audio_output_tokens, rout if raout is None else raout),
            )
            if any(quantity and rate is None for quantity, rate in terms):
                return None  # the call used something this model has no rate for
            total += sum(quantity * rate for quantity, rate in terms if quantity) / 1_000_000
            tokens_priced = True
        units = usage.units or (1 if self.unit == "query" and not usage.tokens else 0)  # a rerank call is one query
        if units and not (tokens_priced and self.kind == "image"):  # image tokens, when reported, are the exact bill
            per = self.unit_rate(variant)
            if per is None:
                return None
            total += units * per
        elif usage.tokens and not tokens_priced:
            return None
        if not tokens_priced and not units and not any(self.rates.values()):
            return None
        factor = (multipliers or {}).get((residency or "").lower(), 1.0)
        return round(total * factor, 10)


class PriceBook:
    def __init__(self, data: dict) -> None:
        self.version: str = data["version"]
        self.providers: dict = data["providers"]
        self.aliases: dict = data["aliases"]
        self.hosts: dict = data.get("hosts", {})
        self.residency: dict = data["residency"]
        self.api_retirements: list = data["api_retirements"]
        self.models: dict[str, Price] = {
            key: Price(key=key, provider=key.split("/", 1)[0], model=key.split("/", 1)[1], **item)
            for key, item in data["models"].items()
        }
        self._folded = {key.lower(): price for key, price in self.models.items()}
        self.lookup = lru_cache(maxsize=8192)(self._lookup)

    def provider_of(self, name: str | None) -> str | None:
        if not name:
            return None
        name = name.lower()
        return self.aliases.get(name, name if name in self.providers else None)

    def provider_for_url(self, url: str | None) -> str | None:
        """The provider behind an API base URL, for OpenAI-compatible clients pointed at another host."""
        host = (urlparse(str(url or "")).hostname or "").lower()
        return next((p for h, p in self.hosts.items() if host == h or host.endswith("." + h)), None)

    def _lookup(self, model: str, provider: str | None = None) -> Price | None:
        """Find a model by the id a provider, gateway or framework reports ("gpt-4o-2024-08-06",
        "models/gemini-2.5-pro", "together_ai/meta-llama/Llama-3.3-70B-Instruct-Turbo", Bedrock ids)."""
        name = model.strip().removeprefix("models/")
        stated = self.provider_of(provider)
        if stated and (price := self._get(f"{stated}/{name}")):
            return price  # the host's own id, such as Together's "Qwen/Qwen3.5-9B" or Groq's "openai/gpt-oss-120b"
        head = self.provider_of(name.split("/", 1)[0]) if "/" in name else None
        if head:
            name = name.split("/", 1)[1]
        if lab := _BEDROCK_LAB.match(name):
            head, name = lab.group(1), lab.group(2)
        # The named lab, then the stated provider, then every provider: OpenAI-compatible clients often point at
        # another host or a gateway while reporting "openai".
        first = [p for p in dict.fromkeys((head, stated)) if p]
        providers = first + [p for p in self.providers if p not in first]
        candidates = dict.fromkeys((name, name.replace(".", "-"), _DATE.sub("", name), _BEDROCK_PROFILE.sub("", name)))
        for index in (self.models, self._folded):  # exact ids first, then ignoring case
            for candidate in candidates:
                for p in providers:
                    key = f"{p}/{candidate}"
                    if price := index.get(key if index is self.models else key.lower()):
                        return price
        return None

    def _get(self, key: str) -> Price | None:
        return self.models.get(key) or self._folded.get(key.lower())

    def cost(self, model: str, usage: Usage, *, provider: str | None = None, **options) -> float | None:
        price = self.lookup(model, provider)
        if price is None:
            return None
        return price.cost(usage, multipliers=self.residency.get(price.provider), **options)


@lru_cache(maxsize=1)
def price_book() -> PriceBook:
    path = Path(__file__).with_name("data") / "prices.json"
    return PriceBook(json.loads(path.read_text(encoding="utf-8")))


def lookup(model: str, provider: str | None = None) -> Price | None:
    return price_book().lookup(model, provider)


def cost(
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    *,
    provider: str | None = None,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    cache_write_1h_tokens: int = 0,
    audio_input_tokens: int = 0,
    audio_output_tokens: int = 0,
    units: float = 0,
    variant: str | None = None,
    batch: bool = False,
    service_tier: str | None = None,
    residency: str | None = None,
) -> float | None:
    """USD cost of one call, or None when the model isn't in the price book. ``units`` are images for image
    models, seconds for video and transcription, characters for speech, queries for rerank, pages for OCR."""
    usage = Usage(input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, cache_write_1h_tokens,
                  audio_input_tokens, audio_output_tokens, units)
    return price_book().cost(
        model, usage, provider=provider, batch=batch, service_tier=service_tier, residency=residency, variant=variant
    )
