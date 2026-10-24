'use client';

import { useState } from 'react';
import { EXAMPLE, MODELS } from '../lib/example';

const dollars = value => value == null ? 'Unknown' : new Intl.NumberFormat('en-US', {style:'currency', currency:'USD', minimumFractionDigits:5, maximumFractionDigits:6}).format(value);

export default function Workbench({ liveEnabled }) {
  const [model, setModel] = useState(MODELS[0]);
  const [mode, setMode] = useState('example');
  const [prompt, setPrompt] = useState(EXAMPLE.prompt);
  const [token, setToken] = useState('');
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [volume, setVolume] = useState(100000);

  async function run(event) {
    event.preventDefault(); setBusy(true); setError(''); setResult(null);
    try {
      const response = await fetch('/api/run', { method:'POST', headers:{'Content-Type':'application/json', ...(mode === 'live' ? {Authorization:`Bearer ${token}`} : {})}, body:JSON.stringify({model, mode, prompt}) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'The request failed.');
      setResult(data);
    } catch (failure) { setError(failure.message || 'Unable to connect. Try again.'); }
    finally { setBusy(false); }
  }

  return <>
    <a className="skip" href="#main">Skip to workbench</a>
    <header><a className="brand" href="https://veqen-app.com">veqen<span aria-hidden="true">↗</span></a><span className="header-label">AI cost starter</span><a href="https://github.com/Keyveve/veqen-sdks/tree/main/examples/vercel-ai-cost-starter">View source ↗</a></header>
    <main id="main">
      <div className="intro"><p className="eyebrow">NEXT.JS · VERCEL AI SDK · VEQEN</p><h1>An AI response.<br/>And its receipt.</h1><p>See what one response costs, then what it means at scale. A small, open-source starting point for cost-aware AI products.</p></div>
      <div className="workbench">
        <section className="request" aria-labelledby="request-title"><div className="section-label"><span>01 / REQUEST</span><span className="status">{mode === 'example' ? 'Recorded example' : 'Live request'}</span></div><h2 id="request-title">Summarize a support ticket</h2>
          <form onSubmit={run}>
            <label htmlFor="model">Model</label><select id="model" value={model} disabled={busy} onChange={e=>{setModel(e.target.value);setResult(null);}}>{MODELS.map(m=><option key={m}>{m}</option>)}</select>
            {liveEnabled && <><label htmlFor="mode">Request mode</label><select id="mode" value={mode} onChange={e=>{setMode(e.target.value);setResult(null);}} disabled={busy}><option value="example">Recorded example · no API call</option><option value="live">Live inference · provider charges apply</option></select></>}
            <label htmlFor="prompt">{mode === 'example' ? 'Example prompt' : 'Your prompt'}</label><textarea id="prompt" rows={5} value={mode === 'example' ? EXAMPLE.prompt : prompt} readOnly={mode === 'example'} maxLength={2000} onChange={e=>setPrompt(e.target.value)} />
            {mode === 'live' && <><label htmlFor="access">Deployment access token</label><input id="access" type="password" autoComplete="off" value={token} onChange={e=>setToken(e.target.value)} required /><p className="fine">Used for this request only. Not stored in your browser.</p></>}
            <button className="primary" disabled={busy}>{busy ? 'Working…' : mode === 'example' ? 'Run recorded example →' : 'Generate a response →'}</button>
            <p className="fine">{mode === 'example' ? 'Fixed sample response and token counts. No inference, credentials or telemetry are sent. Change the model to compare list-price estimates.' : 'One provider request, at most 256 output tokens. The response is priced from reported usage.'}</p>
          </form>
          {error && <p className="error" role="alert">{error}</p>}
          {result && <div className="response" aria-live="polite"><p className="eyebrow">{result.mode === 'example' ? 'RECORDED RESPONSE' : 'MODEL RESPONSE'}</p><p>{result.text}</p></div>}
        </section>
        <section className="receipt" aria-labelledby="receipt-title" aria-live="polite"><div className="section-label"><span>02 / RECEIPT</span><span>USD · LIST PRICE</span></div><h2 id="receipt-title">Every token, accounted for.</h2>
          <div className="total"><span>Estimated cost per response</span><strong>{result ? dollars(result.costUsd) : '—'}</strong><span>{result ? result.model : 'Run the example to see the estimate'}</span></div>
          <dl className="line-items"><div><dt>Fresh input tokens</dt><dd>{result?.usage.inputTokens?.toLocaleString() ?? '—'}</dd></div><div><dt>Cache-read tokens</dt><dd>{result?.usage.cacheReadTokens?.toLocaleString() ?? '—'}</dd></div><div><dt>Output tokens</dt><dd>{result?.usage.outputTokens?.toLocaleString() ?? '—'}</dd></div><div><dt>Price-book version</dt><dd>{result?.priceVersion ?? '—'}</dd></div></dl>
          <div className="projection"><label htmlFor="volume">Monthly responses</label><input id="volume" type="number" min="0" max="1000000000" step="1000" value={volume} onChange={e=>setVolume(Math.max(0, Math.min(1e9, Number(e.target.value)||0)))} /><div className="projected"><span>Projected monthly inference</span><strong>{result?.costUsd != null ? dollars(result.costUsd * volume) : '—'}</strong></div></div>
          <p className="fine">A list-price estimate, not a provider bill. Retries, other infrastructure, discounts and credits can change the total. Model quality must be evaluated separately.</p>
        </section>
      </div>
      <section className="build"><div><p className="eyebrow">TAKE IT INTO YOUR PRODUCT</p><h2>Keep the response.<br/>Keep the cost visible.</h2><p>Use the middleware to record real usage. Add a send-only key when you want costs grouped by customer, feature or agent run in Veqen.</p><a href="https://veqen-app.com/signup?utm_source=vercel&utm_medium=integration&utm_campaign=launch-v1">Open your cost ledger ↗</a></div><pre><code>{`const model = wrapLanguageModel({\n  model: openai("gpt-4o-mini"),\n  middleware: {\n    specificationVersion: "v3",\n    ...veqen({ feature: "support" })\n  }\n});\n\nawait generateText({ model, prompt });\nawait flush();`}</code></pre></section>
    </main><footer><span>Built with Veqen · MIT licensed</span><a href="https://veqen-app.com/docs/price-book">How pricing works ↗</a><a href="https://github.com/Keyveve/veqen-sdks/tree/main/examples/vercel-ai-cost-starter">Deploy your own ↗</a></footer>
  </>;
}
