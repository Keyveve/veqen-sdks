// LangChain.js callback handler:
//   const model = new ChatOpenAI({ model: "gpt-4o-mini", callbacks: [new VeqenCallbackHandler({ feature: "rag" })] });
import { BaseCallbackHandler } from "@langchain/core/callbacks/base";
import { check, currentTags, record } from "./core.js";

export class VeqenCallbackHandler extends BaseCallbackHandler {
  name = "veqen";
  raiseError = true; // let BudgetExceeded stop the call

  constructor(tags = {}) {
    super();
    this.tags = tags;
    this.runs = new Map();
  }

  handleChatModelStart(_llm, _messages, runId, _parentRunId, _extra, _tags, metadata) {
    this.runs.set(runId, metadata ?? {});
    check({ ...this.tags, ...currentTags() });
  }

  handleLLMStart(llm, prompts, runId, parentRunId, extra, tags, metadata) {
    this.handleChatModelStart(llm, prompts, runId, parentRunId, extra, tags, metadata);
  }

  handleLLMError(_error, runId) {
    this.runs.delete(runId);
  }

  handleLLMEnd(output, runId) {
    const meta = this.runs.get(runId) ?? {};
    this.runs.delete(runId);
    for (const generation of output.generations.flat()) {
      const message = generation.message;
      const usage = message?.usage_metadata;
      if (!usage) continue;
      const read = Number(usage.input_token_details?.cache_read ?? 0);
      const write = Number(usage.input_token_details?.cache_creation ?? 0);
      const model = message.response_metadata?.model_name ?? message.response_metadata?.model ?? meta.ls_model_name;
      if (!model) continue;
      record(meta.ls_provider, String(model), {
        inputTokens: usage.input_tokens - read - write,
        outputTokens: usage.output_tokens,
        cacheReadTokens: read,
        cacheWriteTokens: write,
      }, { tags: { ...this.tags, ...currentTags() } });
    }
  }
}
