# OpenLLMetry → Veqen cost ledger

Send provider usage through an OpenTelemetry Collector to [Veqen](https://veqen-app.com/?utm_source=openllmetry&utm_medium=integration&utm_campaign=launch-v1), with customer and feature attribution. Keep your existing tracing backend if you use one; this example is a separate cost pipeline.

Tested with Python `traceloop-sdk==0.62.4`, OpenTelemetry Collector Contrib `0.163.2`, and an actual Azure-hosted OpenAI-compatible request. The request reported 12 input and 4 output tokens; Veqen recorded one attributed call with those counts. Its price-book estimate was $0.0000072. This verifies ingestion and attribution, not agreement with a provider invoice.

## 1. Start the Collector beside your application

Create an **ingest-only** API key in [Veqen settings](https://veqen-app.com/app/settings/keys). Supply it to the Collector as `VEQEN_API_KEY` through your secret manager. Do not put the key in source control or browser code.

Install the [official Collector Contrib release](https://github.com/open-telemetry/opentelemetry-collector-releases/releases/tag/v0.163.2), verify its published checksum, and run:

```sh
otelcol-contrib validate --config collector.yaml
otelcol-contrib --config collector.yaml
```

Use [collector.yaml](collector.yaml). It binds to `127.0.0.1:4318`: the application and Collector must share the host/network namespace. For separate containers, use a private receiver address and restrict access to the application; do not expose an unauthenticated receiver to the internet.

OpenLLMetry's normal HTTP exporter sends protobuf. Veqen accepts OTLP **JSON**. The Collector's `encoding: json` performs this conversion; setting `http/json` on an SDK that only supports protobuf does not. The Collector appends `/v1/traces` to `https://veqen-app.com/v1/otlp`.

## 2. Initialize OpenLLMetry before your model client

```sh
pip install traceloop-sdk==0.62.4 openai
export TRACELOOP_BASE_URL=http://127.0.0.1:4318
export TRACELOOP_TRACE_CONTENT=false
export TRACELOOP_TELEMETRY=false
export TRACELOOP_METRICS_ENABLED=false
export TRACELOOP_LOGGING_ENABLED=false
```

On PowerShell, use `$env:NAME = 'value'` for these environment variables.

```python
from traceloop.sdk import Traceloop
from traceloop.sdk.instruments import Instruments

Traceloop.init(
    app_name="support-service",
    instruments={Instruments.OPENAI},
    telemetry_enabled=False,
    should_enrich_metrics=False,
    resource_attributes={
        "veqen.feature": "support-bot",
        "veqen.project": "customer-support",
        "veqen.environment": "production",
    },
)

from openai import OpenAI
from opentelemetry import trace

client = OpenAI()  # Reads your provider key; Veqen never needs that key.
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Reply with the word ready."}],
)
trace.get_tracer_provider().force_flush(timeout_millis=10000)
```

Resource tags apply to the process, so use them only for stable defaults. For per-request customer attribution, put `veqen.customer` on the **provider usage span**, using your instrumentation's span hook. A span value overrides the resource default. Do not mutate global resource attributes per request in a multi-tenant application. Use pseudonymous IDs, not names, emails, secrets or prompt text, in allocation tags.

## 3. Check the ledger

Look for the feature in [Veqen](https://veqen-app.com/app). The Collector keeps spans with `gen_ai.usage.input_tokens` or `gen_ai.usage.output_tokens`, retains cache usage and maps resource allocation tags onto each span. Retries keep the same trace/span IDs and are deduplicated.

Instrument only one layer that reports usage. If both a framework wrapper and a provider span carry token counts, filter one out; otherwise they represent two different spans and both count. Do not also send the same request through a Veqen SDK wrapper.

This configuration was tested with OpenAI-compatible chat completions. Other instrumentors must report the same modern GenAI token fields and count cached tokens inside total input. Older `prompt_tokens`/`completion_tokens` conventions, provider-specific cache semantics, streaming without final usage, and unsupported modalities need separate validation. Missing usage cannot produce an accurate cost.

## Content and data handling

`TRACELOOP_TRACE_CONTENT=false` disables prompt/completion capture at the source. The Collector drops span events, strips unrelated span/resource/scope attributes, normalizes span names, and clears status messages and trace state. It preserves model, token/cache/tier fields and the five `veqen.*` allocation tags. Trace IDs, timing, scope identifiers and any span links remain OTLP transport metadata: review custom instrumentation and link attributes before using this configuration with it. Veqen stores allocation and usage fields, not arbitrary span contents.

The provided pipeline exports traces only. It does not send cumulative metrics or logs, stop model calls, or enforce a hard spending cap. Provider invoices and negotiated prices still need reconciliation.

## Repeatable local verification

```sh
python test_collector.py /path/to/otelcol-contrib
```

The test uses only loopback HTTP and synthetic data. It verifies two usage spans, exclusion of a non-usage wrapper, cache/tier preservation, per-span overrides, attribution on multiple spans sharing a resource, and removal of sample private attributes/events. No account, API key or paid inference is required.

References: [OpenLLMetry configuration](https://www.traceloop.com/docs/openllmetry/configuration), [Collector HTTP exporter](https://github.com/open-telemetry/opentelemetry-collector/tree/main/exporter/otlphttpexporter), [Veqen OTLP API](https://veqen-app.com/docs/opentelemetry).
