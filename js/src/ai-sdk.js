// Vercel AI SDK middleware:
//   const model = wrapLanguageModel({ model: openai("gpt-4o-mini"), middleware: veqen({ feature: "chat" }) });
// Reads both the AI SDK 5 usage shape (numbers) and the AI SDK 6 shape (objects with totals).
import { check, currentTags, record } from "./core.js";

const n = (v) => Number(v ?? 0);

function toUsage(u = {}) {
  if (typeof u.inputTokens === "object") {
    const read = n(u.inputTokens.cacheRead);
    const write = n(u.inputTokens.cacheWrite);
    return { inputTokens: n(u.inputTokens.total) - read - write, outputTokens: n(u.outputTokens?.total), cacheReadTokens: read, cacheWriteTokens: write };
  }
  const read = n(u.cachedInputTokens);
  return { inputTokens: n(u.inputTokens) - read, outputTokens: n(u.outputTokens), cacheReadTokens: read };
}

export function veqen(defaultTags = {}) {
  const tagsFor = () => ({ ...defaultTags, ...currentTags() });
  const emit = (model, usage, tags, started) => {
    const provider = String(model.provider ?? "").split(".")[0];
    record(provider, model.modelId, toUsage(usage), { tags, latencyMs: Math.round(performance.now() - started) });
  };
  return {
    async wrapGenerate({ doGenerate, model }) {
      const tags = tagsFor();
      check(tags);
      const started = performance.now();
      const result = await doGenerate();
      if (result.usage) emit(model, result.usage, tags, started);
      return result;
    },
    async wrapStream({ doStream, model }) {
      const tags = tagsFor();
      check(tags);
      const started = performance.now();
      const { stream, ...rest } = await doStream();
      const observed = stream.pipeThrough(
        new TransformStream({
          transform(part, controller) {
            if (part.type === "finish" && part.usage) emit(model, part.usage, tags, started);
            controller.enqueue(part);
          },
        }),
      );
      return { stream: observed, ...rest };
    },
  };
}
