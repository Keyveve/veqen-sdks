const vscode = require('vscode');
const book = require('./data/prices.json');
const {createIndex, references, rateSummary} = require('./core.cjs');
const index = createIndex(book);
const languages = ['python','javascript','typescript','javascriptreact','typescriptreact','json','yaml'];

function activate(context) {
  const output = vscode.window.createOutputChannel('Veqen model inventory');
  context.subscriptions.push(output);
  context.subscriptions.push(vscode.languages.registerHoverProvider(languages.map(language=>({language})), {
    provideHover(document, position) {
      if (!vscode.workspace.getConfiguration('veqen').get('hoverEnabled', true)) return;
      const line = document.lineAt(position.line).text;
      const ref = references(line, index).find(r=>position.character >= r.start && position.character <= r.end);
      if (!ref) return;
      const md = new vscode.MarkdownString();
      md.isTrusted = false;
      md.appendText(`Veqen list-price snapshot ${index.version}`);
      for (const item of ref.matches.slice(0, 5)) {
        md.appendMarkdown('\n\n');
        md.appendCodeblock(`${item.key}\n${rateSummary(item)}${item.retires ? `\nRetirement date in book: ${item.retires}` : ''}`, 'text');
      }
      if (ref.matches.length > 1) md.appendText(`\n${ref.matches.length} matching host listings. Choose the provider that bills your calls.`);
      md.appendMarkdown('\n\n');
      md.appendText('Standard list rates only. Cache, batch, tiers, variants and custom pricing can change the cost. Source text is never uploaded.');
      md.appendMarkdown('\n\n[Full pricing rules](https://veqen-app.com/docs/price-book?utm_source=vscode&utm_medium=integration&utm_campaign=launch-v1)');
      return new vscode.Hover(md, new vscode.Range(position.line, ref.start, position.line, ref.end));
    },
  }));
  context.subscriptions.push(vscode.commands.registerCommand('veqen.pricingDocs', () => vscode.env.openExternal(vscode.Uri.parse('https://veqen-app.com/docs/cli?utm_source=vscode&utm_medium=integration&utm_campaign=launch-v1'))));
  context.subscriptions.push(vscode.commands.registerCommand('veqen.scanModels', async () => {
    output.clear(); output.show(true);
    output.appendLine(`Veqen model inventory · price book ${index.version}`);
    output.appendLine('Local quoted-string matches, not usage or a bill. No source code leaves the editor.');
    const files = await vscode.workspace.findFiles('**/*.{py,js,mjs,cjs,jsx,ts,tsx,json,yaml,yml}', '**/{node_modules,.git,.next,dist,build,.venv,venv,vendor}/**', 201);
    if (!files.length) { output.appendLine('No supported source files found in this workspace.'); return; }
    let count = 0;
    let skipped = 0;
    for (const uri of files.slice(0, 200)) {
      try {
        const stat = await vscode.workspace.fs.stat(uri);
        if (stat.size > 500000) { skipped++; continue; }
        const document = await vscode.workspace.openTextDocument(uri);
        for (const ref of references(document.getText(), index)) {
          count++;
          const location = `${vscode.workspace.asRelativePath(uri)}:${document.positionAt(ref.start).line + 1}`;
          output.appendLine(`\n${location}  ${ref.id}`);
          for (const match of ref.matches.slice(0, 5)) output.appendLine(`  ${match.key}: ${rateSummary(match)}`);
          if (ref.matches.length > 5) output.appendLine(`  …and ${ref.matches.length - 5} more host listings; use a provider-qualified identifier.`);
        }
      } catch { skipped++; }
    }
    output.appendLine(`\n${count} references in up to ${Math.min(files.length, 200)} files. ${skipped} oversized or unreadable files skipped.${files.length > 200 ? ' The 200-file limit was reached; this is a partial inventory.' : ''}`);
    output.appendLine('Dynamic model names, escaped strings and unknown models are not recognized. List prices do not imply model availability or equivalent quality.');
  }));
}

module.exports = {activate};
