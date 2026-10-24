# Veqen AI Cost Lens

See AI model prices as you code. Hover a model name to check its price, or find the models used across your project. Everything runs inside your editor. You do not need an account, and your code is never uploaded.

[Install from Open VSX](https://open-vsx.org/extension/Keyveve/veqen-cost-lens). Version 0.1.0 is public; [publisher ownership verification](https://github.com/EclipseFdn/open-vsx.org/issues/14656) is pending, so the listing currently shows an unverified-publisher warning. Microsoft Marketplace publication is still pending separately.

Hover a quoted model such as `"openai/gpt-4o"` or `"gpt-4o"` in Python, JavaScript, TypeScript, JSON or YAML. The extension shows the bundled price-book date and standard rates. When a bare model name matches several billing hosts, it shows the ambiguity rather than selecting a provider for you.

Run **Veqen: Inventory Model References** from the Command Palette to list recognized references and their locations in the output panel. The scan reads at most 200 supported source files, skips files larger than 500 KB and common dependency/build directories, and reports when it is partial. It does not execute project code or invoke a shell. It can operate in an untrusted or virtual workspace.

## Limits

This is a model-reference inventory, not measured spend or an invoice. Dynamic identifiers, escaped strings and models absent from the snapshot are not recognized. Unknown rates remain unknown. Hovers show standard list rates; cache, batch, long-context, image variants, residency and negotiated pricing can differ. A retirement date is shown only when the book records it. The price book updates when the extension updates; the extension makes no background network requests.

Disable hovers with `veqen.hoverEnabled`. The documentation command opens the public Veqen documentation in your browser only when selected. It includes a fixed channel label and sends no source code, file paths or workspace identity.

## Build and install the local package

From this directory, using Node.js 22:

```sh
npm ci --ignore-scripts
npm run prepare-data
npm test
npm run package
```

In VS Code choose **Extensions: Install from VSIX…** and select the generated file. A local build is separate from the published Open VSX version linked above.

The price book comes from `../python/veqen/data/prices.json`. Packaging copies the repository's reviewed snapshot and license notices; it never downloads a price book during editor use.

Packaging uses VSCE 3.7.1 with Azure Identity 4.13.0 and MSAL's UUID dependency pinned to 11.1.1 to avoid the affected MSAL 6.x authentication dependency and the older UUID buffer-bounds advisory. UUID 11 retains the CommonJS `v4()` API used here. These are build-only dependencies, excluded from the VSIX. Recheck these pins and `npm audit` when updating the packager.

[Pricing rules](https://veqen-app.com/docs/price-book) · [SDK and CLI](https://veqen-app.com/docs/cli) · [Report an issue](https://github.com/Keyveve/veqen-sdks/issues)

MIT licensed. See LICENSE and THIRD_PARTY_NOTICES in the package.
