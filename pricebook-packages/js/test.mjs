import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import book from './index.js';

test('the import and raw JSON expose the reviewed snapshot and units', () => {
  const raw = JSON.parse(readFileSync(new URL('./prices.json', import.meta.url), 'utf8'));
  assert.deepEqual(book, raw);
  assert.equal(book.schema, 2);
  assert.ok(Object.keys(book.models).length > 100);
  assert.equal(book.models['openai/gpt-4o'].rates.standard.in, 2.5);
  assert.equal(book.models['openai/gpt-4o'].rates.standard.out, 10);
});
