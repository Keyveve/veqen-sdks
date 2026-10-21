// Official JavaScript/TypeScript client for the Veqen signup-check API. Works anywhere `fetch` exists.

const DEFAULT_BASE_URL = "https://veqen-app.com";
const RETRY_STATUSES = new Set([429, 500, 502, 503, 504]);
const VERSION = "0.1.0";

export class VeqenError extends Error {
  constructor(status, type, message, requestId) {
    super(`${status} ${type}: ${message}`);
    this.name = "VeqenError";
    this.status = status;
    this.type = type;
    this.requestId = requestId;
  }
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const env = (name) => (typeof process !== "undefined" && process.env ? process.env[name] : undefined);

export class Veqen {
  constructor(options = {}) {
    this.apiKey = options.apiKey ?? env("VEQEN_API_KEY");
    if (!this.apiKey) throw new Error("Pass { apiKey } or set VEQEN_API_KEY.");
    this.baseUrl = (options.baseUrl ?? env("VEQEN_BASE_URL") ?? DEFAULT_BASE_URL).replace(/\/+$/, "");
    this.timeoutMs = options.timeoutMs ?? 10000;
    this.maxRetries = options.maxRetries ?? 2;
    this.fetch = options.fetch ?? globalThis.fetch.bind(globalThis);
  }

  email(email, { verifyMailbox = false, idempotencyKey } = {}) {
    return this.#post("/v1/email/check", { email, verify_mailbox: verifyMailbox }, idempotencyKey);
  }

  async emails(emails, { verifyMailbox = false } = {}) {
    const results = [];
    for (let start = 0; start < emails.length; start += 100) {
      const chunk = emails.slice(start, start + 100);
      const data = await this.#post("/v1/email/batch", { emails: chunk, verify_mailbox: verifyMailbox });
      results.push(...data.results);
    }
    return results;
  }

  ip(ip, { idempotencyKey } = {}) {
    return this.#post("/v1/ip/check", { ip }, idempotencyKey);
  }

  phone(phone, { country, idempotencyKey } = {}) {
    return this.#post("/v1/phone/check", { phone, country }, idempotencyKey);
  }

  domain(domain, { idempotencyKey } = {}) {
    return this.#post("/v1/domain/check", { domain }, idempotencyKey);
  }

  signup({ email, ip, phone, phoneCountry, verifyMailbox = false, idempotencyKey } = {}) {
    const body = { email, ip, phone, phone_country: phoneCountry, verify_mailbox: verifyMailbox };
    for (const key of Object.keys(body)) if (body[key] === undefined || body[key] === null || body[key] === "") delete body[key];
    return this.#post("/v1/signup/check", body, idempotencyKey);
  }

  account() {
    return this.#request("GET", "/v1/account");
  }

  usage(days = 30) {
    return this.#request("GET", `/v1/usage?days=${encodeURIComponent(days)}`);
  }

  #post(path, body, idempotencyKey) {
    // One key per logical call, shared by all retries to prevent double charging.
    return this.#request("POST", path, body, idempotencyKey ?? globalThis.crypto.randomUUID());
  }

  async #request(method, path, body, idempotencyKey) {
    const headers = {
      Authorization: `Bearer ${this.apiKey}`,
      Accept: "application/json",
      "User-Agent": `veqen-js/${VERSION}`,
    };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;

    for (let attempt = 0; ; attempt += 1) {
      let response;
      try {
        response = await this.fetch(`${this.baseUrl}${path}`, {
          method,
          headers,
          body: body === undefined ? undefined : JSON.stringify(body),
          signal: AbortSignal.timeout(this.timeoutMs),
        });
      } catch (error) {
        if (attempt >= this.maxRetries) throw error;
        await sleep(Math.min(250 * 2 ** (attempt + 1), 4000));
        continue;
      }
      if (RETRY_STATUSES.has(response.status) && attempt < this.maxRetries) {
        const retryAfter = Number(response.headers.get("Retry-After"));
        await sleep(retryAfter > 0 ? retryAfter * 1000 : Math.min(250 * 2 ** (attempt + 1), 4000));
        continue;
      }
      let data = null;
      try {
        data = await response.json();
      } catch {
        data = null;
      }
      if (!response.ok) {
        const error = (data && data.error) || {};
        throw new VeqenError(response.status, error.type || "http_error", error.message || response.statusText, response.headers.get("X-Request-Id"));
      }
      return data;
    }
  }
}

export default Veqen;
