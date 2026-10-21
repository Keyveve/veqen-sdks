# @veqen/sdk

Official JavaScript/TypeScript client for [Veqen](https://veqen-app.com). Catch disposable emails, typos, datacenter and Tor IPs, and VoIP numbers with one call. Zero dependencies; runs on Node 20+ and server runtimes with fetch and crypto.randomUUID. Keep API keys out of browser code.

```bash
npm install https://veqen-app.com/static/sdk/veqen-sdk-0.1.0.tgz
```

```javascript
import { Veqen } from "@veqen/sdk";

const veqen = new Veqen(); // reads VEQEN_API_KEY
const { risk } = await veqen.signup({ email: "jane@mailinator.com", ip: "185.220.101.1" });

if (risk.verdict === "refuse") {
  // block, or ask for a different email
}
```

Methods: `email()`, `emails()`, `ip()`, `phone()`, `domain()`, `signup()`, `account()`, `usage()`. Errors throw `VeqenError` with `.status`, `.type` and `.requestId`. 429 and 5xx responses are retried automatically.

Docs: https://veqen-app.com/docs
