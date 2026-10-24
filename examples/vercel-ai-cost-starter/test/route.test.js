import test from 'node:test';
import assert from 'node:assert/strict';
import { POST } from '../app/api/run/route.js';

const request = body => new Request('http://localhost/api/run', {method:'POST',body:JSON.stringify(body)});
test('recorded fixture works without credentials and cannot become a model request', async () => {
  const response = await POST(request({model:'gpt-4o-mini',mode:'example',prompt:'ignored fixture input'}));
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.mode, 'example');
  assert.equal(body.usage.inputTokens, 1280);
  assert.ok(body.costUsd > 0);
});
test('live calls are refused without configuration or the deployment token', async () => {
  delete process.env.OPENAI_API_KEY;
  delete process.env.DEMO_ACCESS_TOKEN;
  assert.equal((await POST(request({model:'gpt-4o-mini',mode:'live',prompt:'hello'}))).status, 503);
  process.env.OPENAI_API_KEY = 'test-not-a-provider-key';
  process.env.DEMO_ACCESS_TOKEN = 'x'.repeat(32);
  assert.equal((await POST(request({model:'gpt-4o-mini',mode:'live',prompt:'hello'}))).status, 401);
  delete process.env.OPENAI_API_KEY;
  delete process.env.DEMO_ACCESS_TOKEN;
});
test('chunked oversize requests are refused before parsing', async () => {
  assert.equal((await POST(request({padding:'x'.repeat(9000)}))).status, 413);
});
