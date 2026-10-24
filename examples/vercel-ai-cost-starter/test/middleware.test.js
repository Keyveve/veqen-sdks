import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, unlinkSync, rmdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { generateText, wrapLanguageModel } from 'ai';
import { MockLanguageModelV3 } from 'ai/test';
import { init, withTags } from '@veqen/sdk';
import { veqen } from '@veqen/sdk/ai-sdk';

test('AI SDK 6 middleware records real usage shape and run attribution once', async () => {
  const directory = mkdtempSync(join(tmpdir(), 'veqen-starter-'));
  const ledger = join(directory, 'calls.jsonl');
  init({apiKey:'',ledgerFile:ledger});
  try {
    const model = wrapLanguageModel({model:new MockLanguageModelV3({provider:'openai.responses',modelId:'gpt-4o',doGenerate:{
      content:[{type:'text',text:'fixture result'}],finishReason:{unified:'stop',raw:'stop'},warnings:[],
      usage:{inputTokens:{total:100,noCache:80,cacheRead:20,cacheWrite:0},outputTokens:{total:10,text:10,reasoning:0}},
    }}),middleware:{specificationVersion:'v3',...veqen({feature:'support'})}});
    const result = await withTags({run:'test-run'},()=>generateText({model,prompt:'fixture'}));
    assert.equal(result.text, 'fixture result');
    const rows = readFileSync(ledger,'utf8').trim().split('\n').map(JSON.parse);
    assert.equal(rows.length, 1);
    assert.equal(rows[0].run, 'test-run');
    assert.equal(rows[0].input_tokens, 80);
    assert.equal(rows[0].cache_read_tokens, 20);
    assert.equal(rows[0].cost_usd, .000325);
  } finally { init({apiKey:'',ledgerFile:''}); unlinkSync(ledger); rmdirSync(directory); }
});
