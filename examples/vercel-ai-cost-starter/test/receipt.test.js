import test from 'node:test';
import assert from 'node:assert/strict';
import { receipt, reportedUsage, validateInput } from '../lib/receipt.js';

test('cache reads are separate from fresh tokens', () => {
  const r = receipt('gpt-4o', {inputTokens:2000,cacheReadTokens:8000,outputTokens:500});
  assert.equal(r.costUsd, .02);
  assert.match(r.priceVersion, /^\d{4}-\d{2}-\d{2}$/);
});
test('unknown price stays unknown', () => assert.equal(receipt('nonexistent-xyz', {}).costUsd, null));
test('missing or contradictory provider usage is not a free response', () => {
  assert.equal(receipt('gpt-4o', reportedUsage({})).costUsd, null);
  assert.equal(receipt('gpt-4o', reportedUsage({inputTokens: 10, outputTokens: 5, inputTokenDetails: {cacheReadTokens: 20}})).costUsd, null);
  assert.equal(receipt('gpt-4o', reportedUsage({inputTokens: 0, outputTokens: 0})).costUsd, 0);
});
test('live calls require a bounded prompt and allowlisted model', () => {
  assert.equal(validateInput({model:'gpt-4o-mini',mode:'live',prompt:'hello'}), true);
  for (const body of [{model:'gpt-4o-mini',mode:'live',prompt:''},{model:'external/model',mode:'live',prompt:'hello'},{model:'gpt-4o',mode:'live',prompt:'a'.repeat(2001)}]) assert.equal(validateInput(body), false);
});
