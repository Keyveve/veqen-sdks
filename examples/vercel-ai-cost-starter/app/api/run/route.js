import { timingSafeEqual } from 'node:crypto';
import { generateText, wrapLanguageModel } from 'ai';
import { openai } from '@ai-sdk/openai';
import { veqen } from '@veqen/sdk/ai-sdk';
import { flush, withTags } from '@veqen/sdk';
import { EXAMPLE, receipt, reportedUsage, validateInput } from '../../../lib/receipt.js';

export const runtime = 'nodejs';
export const maxDuration = 30;

function reply(value, status = 200) {
  return Response.json(value, { status, headers: { 'Cache-Control': 'no-store' } });
}

export async function POST(request) {
  if (Number(request.headers.get('content-length') || 0) > 8192) return reply({ error: 'Request too large.' }, 413);
  const reader = request.body?.getReader();
  let bytes = 0;
  const chunks = [];
  if (reader) {
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      bytes += value.byteLength;
      if (bytes > 8192) { await reader.cancel(); return reply({ error: 'Request too large.' }, 413); }
      chunks.push(Buffer.from(value));
    }
  }
  const raw = Buffer.concat(chunks).toString('utf8');
  let body;
  try { body = JSON.parse(raw); } catch { return reply({ error: 'Expected JSON.' }, 400); }
  if (!validateInput(body)) return reply({ error: 'Choose a supported model and a prompt of 1–2,000 characters.' }, 400);
  if (body.mode === 'example') return reply({ ...receipt(body.model, EXAMPLE.usage), text: EXAMPLE.text, mode: 'example' });

  const expected = process.env.DEMO_ACCESS_TOKEN;
  if (!process.env.OPENAI_API_KEY || !expected || expected.length < 32) return reply({ error: 'Live inference is not configured.' }, 503);
  const supplied = request.headers.get('authorization')?.replace(/^Bearer /, '') || '';
  if (Buffer.byteLength(supplied) !== Buffer.byteLength(expected) || !timingSafeEqual(Buffer.from(supplied), Buffer.from(expected))) {
    return reply({ error: 'A valid deployment access token is required.' }, 401);
  }
  try {
    const model = wrapLanguageModel({ model: openai(body.model), middleware: { specificationVersion: 'v3', ...veqen({ feature: 'cost-starter' }) } });
    const result = await withTags({ run: crypto.randomUUID(), environment: 'starter' }, () => generateText({
      model, prompt: body.prompt, maxOutputTokens: 256, maxRetries: 0, abortSignal: AbortSignal.timeout(20000),
    }));
    const usage = reportedUsage(result.usage);
    return reply({ ...receipt(body.model, usage), text: result.text, mode: 'live' });
  } catch {
    return reply({ error: 'The model request failed. Check the provider configuration in your deployment.' }, 502);
  } finally {
    await flush();
  }
}
