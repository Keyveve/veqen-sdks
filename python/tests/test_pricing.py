import json
from pathlib import Path

import pytest

import veqen
from veqen.pricing import Price, Usage


def test_basic_cost_matches_rate_card():
    # gpt-4o: $2.50 in / $10 out per million
    assert veqen.cost("gpt-4o", 1_000, 500) == pytest.approx(0.0075)


def test_cache_reads_writes_and_one_hour_writes():
    # claude-sonnet-4-5: in 3, out 15, cache read 0.30, 5m write 3.75, 1h write 6 per million
    usage = dict(cache_read_tokens=10_000, cache_write_tokens=2_000, cache_write_1h_tokens=1_000)
    expected = (1_000 * 3 + 500 * 15 + 10_000 * 0.30 + 2_000 * 3.75 + 1_000 * 6) / 1e6
    assert veqen.cost("claude-sonnet-4-5", 1_000, 500, **usage) == pytest.approx(expected)


def test_batch_and_service_tiers():
    assert veqen.cost("gpt-4o", 1_000_000, 0, batch=True) == pytest.approx(1.25)
    assert veqen.cost("gpt-4o", 1_000_000, 0, service_tier="priority") == pytest.approx(4.25)
    assert veqen.cost("gpt-4o", 1_000_000, 0, service_tier="default") == pytest.approx(2.50)


def test_long_context_tier_uses_whole_prompt():
    # Haiku 5.5: $0.10/$0.50 up to 100K prompt tokens, $0.50/$2.50 above
    assert veqen.cost("claude-haiku-5-5", 90_000, 1_000) == pytest.approx((90_000 * 0.10 + 1_000 * 0.50) / 1e6)
    assert veqen.cost("claude-haiku-5-5", 50_000, 1_000, cache_read_tokens=60_000) == pytest.approx(
        (50_000 * 0.50 + 1_000 * 2.50 + 60_000 * 0.05) / 1e6
    )


def test_residency_multiplier_applies_to_anthropic_only():
    base = veqen.cost("claude-sonnet-4-5", 1_000_000, 0)
    assert veqen.cost("claude-sonnet-4-5", 1_000_000, 0, residency="us") == pytest.approx(base * 1.1)
    assert veqen.cost("gpt-4o", 1_000_000, 0, residency="us") == pytest.approx(2.5)


def test_missing_mode_rates_derive_from_the_input_discount():
    price = Price("x/m", "x", "m", {"standard": {"in": 2.0, "out": 8.0, "cw": 2.5}, "batch": {"in": 1.0, "out": 4.0}})
    assert price.rate("cw", "batch") == pytest.approx(1.25)
    assert price.cost(Usage(cache_write_tokens=1_000_000), batch=True) == pytest.approx(1.25)
    assert price.cost(Usage(cache_read_tokens=1_000_000)) == pytest.approx(2.0)  # no cache price: billed as input


@pytest.mark.parametrize(
    ("reported", "provider", "key"),
    [
        ("gpt-4o-2024-08-06", None, "openai/gpt-4o-2024-08-06"),
        ("anthropic/claude-sonnet-4.5", None, "anthropic/claude-sonnet-4-5"),
        ("us.anthropic.claude-sonnet-4-5-20250929-v1:0", "bedrock", "anthropic/claude-sonnet-4-5-20250929"),
        ("models/gemini-2.5-flash", "google", "google/gemini-2.5-flash"),
        ("deepseek-chat", "openai", "deepseek/deepseek-chat"),
        ("gpt-4o", "azure", "openai/gpt-4o"),
        ("Qwen/Qwen3.5-9B", "together", "together/Qwen/Qwen3.5-9B"),  # a host's id that starts with a provider name
        ("openai/gpt-oss-120b", "groq", "groq/openai/gpt-oss-120b"),
        ("together_ai/meta-llama/Llama-3.3-70B-Instruct-Turbo", None,
         "together/meta-llama/Llama-3.3-70B-Instruct-Turbo"),
        ("fal-ai/flux/dev", "fal", "fal/fal-ai/flux/dev"),
    ],
)
def test_lookup_resolves_ids_from_providers_gateways_and_clouds(reported, provider, key):
    assert veqen.lookup(reported, provider).key == key


def test_models_billed_per_unit_with_variants():
    image = veqen.lookup("gpt-image-1")
    assert (image.kind, image.unit) == ("image", "image")
    high = image.unit_rate("high/1024x1024")
    assert high and high > image.unit_rate("low/1024x1024")
    assert veqen.cost("gpt-image-1", units=3, variant="high/1024-x-1024") == pytest.approx(3 * high)
    same_size = sorted(k[2:] for k in image.rates if k.endswith("/1024x1024"))[0]
    assert image.unit_rate("ultra/1024x1024") == image.unit_rate(same_size)  # unknown quality: same size, any quality
    # image tokens, when reported, are the bill: the per-image rate isn't added on top
    assert image.cost(Usage(1_000, 4_000, units=1)) == pytest.approx(image.cost(Usage(1_000, 4_000)))
    assert veqen.cost("whisper-1", units=600) == pytest.approx(0.06)  # $0.006 a minute
    assert veqen.cost("tts-1", units=1_000_000) == pytest.approx(15.0)  # $15 per million characters
    rerank = veqen.lookup("rerank-v3.5", "cohere")
    assert rerank.cost(Usage()) == pytest.approx(rerank.unit_rate())  # a rerank call is one query


def test_audio_tokens_and_rates_a_model_lacks():
    std = veqen.lookup("gpt-realtime").rates["standard"]
    expected = (100 * std["in"] + 4_000 * std["ain"] + 50 * std["out"] + 2_000 * std["aout"]) / 1e6
    priced = veqen.cost("gpt-realtime", 100, 50, audio_input_tokens=4_000, audio_output_tokens=2_000)
    assert priced == pytest.approx(expected)
    only_input = Price("x/e", "x", "e", {"standard": {"in": 0.02}}, kind="embedding")
    assert only_input.cost(Usage(1_000_000)) == pytest.approx(0.02)
    assert only_input.cost(Usage(1_000, 10)) is None  # output tokens on a model with no output rate
    assert veqen.cost("veo-3.1-generate-001", 1_000, 0) is None  # tokens on a model billed per second


def test_provider_for_url_reads_openai_compatible_hosts():
    book = veqen.pricing.price_book()
    assert book.provider_for_url("https://api.together.xyz/v1") == "together"
    assert book.provider_for_url("https://my-resource.openai.azure.com/openai") == "openai"
    assert book.provider_for_url("https://x.services.ai.azure.com/models") == "azure-ai"
    assert book.provider_for_url("http://vllm.internal:8000/v1") is None
    assert book.provider_for_url(None) is None


def test_an_exact_id_beats_one_that_differs_only_in_case():
    from veqen.pricing import PriceBook

    models = {"a/Model-X": {"rates": {"standard": {"in": 1}}}, "b/model-x": {"rates": {"standard": {"in": 2}}}}
    book = PriceBook({"version": "x", "providers": {"a": {}, "b": {}}, "aliases": {}, "hosts": {}, "residency": {},
                      "api_retirements": [], "models": models})
    assert book.lookup("model-x").key == "b/model-x" and book.lookup("Model-X").key == "a/Model-X"
    assert book.lookup("MODEL-X").key == "a/Model-X"  # no exact match anywhere: the first provider, ignoring case
    maverick = "Llama-4-Maverick-17B-128E-Instruct-FP8"
    assert veqen.lookup(maverick).key == f"azure-ai/{maverick}"


def test_unknown_model_is_unpriced():
    assert veqen.lookup("my-finetune-v3") is None
    assert veqen.cost("my-finetune-v3", 10, 10) is None


def test_bundled_price_books_are_identical():
    root = Path(__file__).resolve().parents[2]
    python = (root / "python" / "veqen" / "data" / "prices.json").read_text(encoding="utf-8")
    js = (root / "js" / "src" / "prices.js").read_text(encoding="utf-8")
    assert js == f"export default {python.rstrip()};\n"
    assert len(json.loads(python)["models"]) > 100
