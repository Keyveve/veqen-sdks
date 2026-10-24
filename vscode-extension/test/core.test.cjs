const test = require('node:test');
const assert = require('node:assert/strict');
const {createIndex, references, rateSummary} = require('../core.cjs');
const index = createIndex({version:'2026-10-23',models:{
  'openai/model':{rates:{standard:{in:2,out:8}}},
  'azure-ai/model':{rates:{standard:{in:3,out:9}}},
  'vendor/image':{unit:'image',rates:{standard:{unit:0}}},
}});
test('bare names preserve billing-host ambiguity', () => {
  assert.equal(index.matches('model').length, 2);
  assert.equal(index.matches('openai/model').length, 1);
  assert.deepEqual(index.matches('unknown'), []);
});
test('only literal known references are matched with correct positions', () => {
  const source = 'model = "openai/model"; other = `model`; dynamic = `${model}`';
  const refs = references(source, index);
  assert.equal(refs.length, 2);
  for (const ref of refs) assert.equal(source.slice(ref.start, ref.end), ref.id);
});
test('unknown and zero rates are distinct', () => {
  assert.equal(rateSummary({rates:{standard:{}}}), 'unknown input · unknown output / 1M tokens');
  assert.equal(rateSummary(index.matches('vendor/image')[0]), '$0 / image');
});
test('escaped strings are not guessed', () => assert.deepEqual(references('"openai\\/model"', index), []));
