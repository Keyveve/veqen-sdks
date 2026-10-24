// The price book: exact USD cost for any priced inference call. Text, embedding and realtime models are
// priced per token (caching, batch, service tiers, long-context tiers, residency); image, video, speech,
// transcription, rerank and OCR models per unit (image, second, character, query, page), with size,
// quality and resolution variants. Works offline from the bundled price book.
import data from "./prices.js";

const DATE = /-(\d{8}|\d{4}-\d{2}-\d{2}|\d{3})$/;
const BEDROCK_LAB = /^(?:[a-z]{2,7}\.)?(anthropic|openai|mistral|deepseek)\.(.+?)(?:-v\d+(?::\d+)?)?$/;
const BEDROCK_PROFILE = /^(?:us|eu|apac|jp|au|ca|global|us-gov)\.(?=[a-z0-9-]+\.)/;
const MODES = { batch: "batch", priority: "priority", flex: "flex" };
const folded = new Map(Object.keys(data.models).map((key) => [key.toLowerCase(), key]));
const found = new Map(); // lookup cache: the same few models are priced over and over

export const priceBook = {
  version: data.version,
  providers: data.providers,
  apiRetirements: data.api_retirements,
  models: data.models,
};

export function providerOf(name) {
  if (!name) return null;
  const lower = String(name).toLowerCase();
  return data.aliases[lower] ?? (lower in data.providers ? lower : null);
}

/** The provider behind an API base URL, for OpenAI-compatible clients pointed at another host. */
export function providerForUrl(url) {
  let host = "";
  try {
    host = new URL(String(url)).hostname.toLowerCase();
  } catch {
    return null;
  }
  const match = Object.entries(data.hosts ?? {}).find(([h]) => host === h || host.endsWith(`.${h}`));
  return match ? match[1] : null;
}

function get(key, exact = false) {
  const found = data.models[key] ? key : exact ? null : folded.get(key.toLowerCase());
  return found ? { key: found, provider: found.split("/")[0], model: found.slice(found.indexOf("/") + 1), kind: "text", ...data.models[found] } : null;
}

function find(model, provider) {
  let name = String(model).trim().replace(/^models\//, "");
  const stated = providerOf(provider);
  let head = name.includes("/") ? providerOf(name.split("/")[0]) : null;
  // The host's own id, such as Together's "Qwen/Qwen3.5-9B" or Bedrock's under a "us." profile, as stated or named
  for (const [host, own] of [[stated, name], [head, name.slice(name.indexOf("/") + 1)]]) {
    const price = host && (get(`${host}/${own}`) ?? get(`${host}/${own.replace(BEDROCK_PROFILE, "")}`));
    if (price) return price;
  }
  if (head) name = name.slice(name.indexOf("/") + 1);
  const lab = BEDROCK_LAB.exec(name);
  if (lab) [, head, name] = lab;
  // The named lab, then the stated provider, then every provider: OpenAI-compatible clients often point elsewhere.
  const first = [...new Set([head, stated])].filter(Boolean);
  const order = [...first, ...Object.keys(data.providers).filter((p) => !first.includes(p))];
  const candidates = new Set([name, name.replaceAll(".", "-"), name.replace(DATE, ""), name.replace(BEDROCK_PROFILE, "")]);
  for (const exact of [true, false]) { // exact ids first, then ignoring case
    for (const candidate of candidates) {
      for (const p of order) {
        const price = get(`${p}/${candidate}`, exact);
        if (price) return price;
      }
    }
  }
  return null;
}

export function lookup(model, provider) {
  const cacheKey = `${provider ?? ""}\u0000${model}`;
  if (!found.has(cacheKey)) {
    if (found.size > 8192) found.clear();
    found.set(cacheKey, find(model, provider));
  }
  return found.get(cacheKey);
}

function rate(price, field, mode, tier) {
  const exact = price.rates[tier ? `${mode}>${tier}` : mode]?.[field];
  if (exact != null) return exact;
  const base = price.rates[tier ? `standard>${tier}` : "standard"]?.[field];
  if (base == null) return tier ? rate(price, field, mode, null) : null;
  const modeIn = price.rates[mode]?.in;
  const stdIn = price.rates.standard?.in;
  return mode !== "standard" && modeIn && stdIn ? (base * modeIn) / stdIn : base;
}

/** USD per unit for a variant ("hd/1024x1792", "1080p"), then the same size at any quality, then standard. */
export function unitRate(price, variant) {
  if (variant) {
    const v = String(variant).toLowerCase().replaceAll("-x-", "x");
    const exact = price.rates[`v:${v}`]?.unit;
    if (exact != null) return exact;
    const size = v.split("/").pop();
    const sameSize = Object.keys(price.rates).filter((k) => k.startsWith("v:") && k.endsWith(`/${size}`)).sort();
    if (sameSize.length) return price.rates[sameSize[0]].unit;
  }
  return price.rates.standard?.unit ?? null;
}

/** USD cost of a call to `price`, or null when the call used something the model has no rate for. */
export function priceCall(price, usage, { batch = false, serviceTier, residency, variant } = {}) {
  const u = {
    inputTokens: 0, outputTokens: 0, cacheReadTokens: 0, cacheWriteTokens: 0, cacheWrite1hTokens: 0,
    audioInputTokens: 0, audioOutputTokens: 0, units: 0, ...usage,
  };
  const prompt = u.inputTokens + u.cacheReadTokens + u.cacheWriteTokens + u.cacheWrite1hTokens + u.audioInputTokens;
  const tokens = prompt + u.outputTokens + u.audioOutputTokens;
  const tiers = Object.keys(price.rates).filter((k) => k.includes(">")).map((k) => Number(k.split(">")[1]));
  const tier = Math.max(...tiers.filter((t) => prompt > t), 0) || null;
  const mode = batch ? "batch" : MODES[String(serviceTier ?? "").toLowerCase()] ?? "standard";
  const rin = rate(price, "in", mode, tier);
  const rout = rate(price, "out", mode, tier);
  let total = 0;
  let tokensPriced = false;
  if (tokens && (rin != null || rout != null)) {
    const rcw = rate(price, "cw", mode, tier) ?? rin;
    const terms = [
      [u.inputTokens, rin],
      [u.outputTokens, rout],
      [u.cacheReadTokens, rate(price, "cr", mode, tier) ?? rin],
      [u.cacheWriteTokens, rcw],
      [u.cacheWrite1hTokens, rate(price, "cw1h", mode, tier) ?? rcw],
      [u.audioInputTokens, rate(price, "ain", mode, tier) ?? rin],
      [u.audioOutputTokens, rate(price, "aout", mode, tier) ?? rout],
    ];
    if (terms.some(([quantity, r]) => quantity && r == null)) return null; // used something this model has no rate for
    total += terms.reduce((sum, [quantity, r]) => sum + (quantity ? quantity * r : 0), 0) / 1_000_000;
    tokensPriced = true;
  }
  const units = u.units || (price.unit === "query" && !tokens ? 1 : 0); // a rerank call is one query
  if (units && !(tokensPriced && price.kind === "image")) { // image tokens, when reported, are the exact bill
    const per = unitRate(price, variant);
    if (per == null) return null;
    total += units * per;
  } else if (tokens && !tokensPriced) {
    return null;
  }
  const factor = data.residency[price.provider]?.[String(residency ?? "").toLowerCase()] ?? 1;
  return Math.round(total * factor * 1e10) / 1e10;
}

/** USD cost of one call, or null when the model isn't in the price book. */
export function cost(model, usage, options = {}) {
  const price = lookup(model, options.provider);
  return price ? priceCall(price, usage, options) : null;
}
