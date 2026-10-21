import assert from "node:assert/strict";
import { test } from "node:test";
import { Veqen, VeqenError } from "../src/index.js";

function mockFetch(handler) {
  const calls = [];
  const fetch = async (url, init) => {
    calls.push({ url, init });
    const { status = 200, body = {}, headers = {} } = await handler(url, init, calls.length);
    return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...headers } });
  };
  return { fetch, calls };
}

test("signup sends auth and drops empty fields", async () => {
  const { fetch, calls } = mockFetch(() => ({ body: { risk: { verdict: "refuse" } } }));
  const client = new Veqen({ apiKey: "vq_live_test", baseUrl: "https://api.test/", fetch });
  const result = await client.signup({ email: "a@b.com", ip: "1.2.3.4" });
  assert.equal(result.risk.verdict, "refuse");
  assert.equal(calls[0].url, "https://api.test/v1/signup/check");
  assert.equal(calls[0].init.headers.Authorization, "Bearer vq_live_test");
  assert.deepEqual(JSON.parse(calls[0].init.body), { email: "a@b.com", ip: "1.2.3.4", verify_mailbox: false });
});

test("errors carry the API error type", async () => {
  const { fetch } = mockFetch(() => ({ status: 402, body: { error: { type: "insufficient_credits", message: "Buy credits" } }, headers: { "X-Request-Id": "r1" } }));
  const client = new Veqen({ apiKey: "k", baseUrl: "https://api.test", fetch, maxRetries: 0 });
  await assert.rejects(client.email("a@b.com"), (error) => {
    assert.ok(error instanceof VeqenError);
    assert.equal(error.type, "insufficient_credits");
    assert.equal(error.status, 402);
    assert.equal(error.requestId, "r1");
    return true;
  });
});

test("retries 429 using Retry-After", async () => {
  const { fetch, calls } = mockFetch((url, init, n) => (n === 1 ? { status: 429, body: {}, headers: { "Retry-After": "0" } } : { body: { ok: true } }));
  const client = new Veqen({ apiKey: "k", baseUrl: "https://api.test", fetch });
  assert.deepEqual(await client.ip("1.2.3.4"), { ok: true });
  assert.equal(calls.length, 2);
});

test("batch chunks by 100", async () => {
  const sizes = [];
  const { fetch } = mockFetch((url, init) => {
    const emails = JSON.parse(init.body).emails;
    sizes.push(emails.length);
    return { body: { results: emails.map((email) => ({ email })), count: emails.length } };
  });
  const client = new Veqen({ apiKey: "k", baseUrl: "https://api.test", fetch });
  const results = await client.emails(Array.from({ length: 230 }, (_, i) => `u${i}@a.com`));
  assert.deepEqual(sizes, [100, 100, 30]);
  assert.equal(results.length, 230);
});

test("requires a key", () => {
  const saved = process.env.VEQEN_API_KEY;
  delete process.env.VEQEN_API_KEY;
  assert.throws(() => new Veqen());
  if (saved) process.env.VEQEN_API_KEY = saved;
});

test("a lost response retries with the same automatic idempotency key", async () => {
  const keys = [];
  const fetch = async (url, init) => {
    keys.push(init.headers["Idempotency-Key"]);
    if (keys.length === 1) throw new Error("Response lost after server charged");
    return new Response("{}", { status: 200 });
  };
  const client = new Veqen({ apiKey: "k", fetch });
  await client.ip("1.2.3.4");
  await client.ip("1.2.3.4");
  assert.ok(keys[0]);
  assert.equal(keys[0], keys[1]);
  assert.notEqual(keys[1], keys[2]);
});
