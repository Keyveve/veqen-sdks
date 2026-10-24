import { cost, priceBook } from '@veqen/sdk';

import { MODELS } from './example.js';
export { EXAMPLE, MODELS } from './example.js';

export function receipt(model, usage) {
  const complete = ['inputTokens', 'outputTokens', 'cacheReadTokens'].every(key => Number.isFinite(usage[key]) && usage[key] >= 0);
  return { model, usage, costUsd: complete ? cost(model, usage) : null, priceVersion: priceBook.version };
}

export function reportedUsage(usage = {}) {
  const cached = usage.inputTokenDetails?.cacheReadTokens ?? 0;
  return {
    inputTokens: Number.isFinite(usage.inputTokens) && cached <= usage.inputTokens ? usage.inputTokens - cached : null,
    outputTokens: usage.outputTokens ?? null,
    cacheReadTokens: cached,
  };
}

export function validateInput(body) {
  if (!body || !MODELS.includes(body.model) || !['example', 'live'].includes(body.mode)) return false;
  return body.mode === 'example' || (typeof body.prompt === 'string' && body.prompt.trim().length > 0 && body.prompt.length <= 2000);
}
