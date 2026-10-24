function createIndex(book) {
  const exact = new Map(Object.entries(book.models));
  const bare = new Map();
  for (const key of exact.keys()) {
    const model = key.slice(key.indexOf('/') + 1);
    if (!bare.has(model)) bare.set(model, []);
    bare.get(model).push(key);
  }
  return {
    version: book.version,
    matches(id) {
      // A host-qualified identifier is exact. A bare identifier can be ambiguous;
      // show every matching host rather than assigning a guessed billing provider.
      const keys = exact.has(id) ? [id] : bare.get(id) || [];
      return keys.map(key => ({key, ...exact.get(key)}));
    },
  };
}

function references(text, index) {
  const results = [];
  const quoted = /(["'`])([^"'`\r\n]{1,200})\1/g;
  for (const match of text.matchAll(quoted)) {
    if (match[2].includes('${') || match[2].includes('\\')) continue;
    const found = index.matches(match[2]);
    if (found.length) results.push({id:match[2], start:match.index + 1, end:match.index + 1 + match[2].length, matches:found});
  }
  return results;
}

function rateSummary(model) {
  const standard = model.rates?.standard || {};
  const usd = value => value == null ? 'unknown' : `$${value}`;
  if (model.unit) return `${usd(standard.unit)} / ${model.unit}`;
  return `${usd(standard.in)} input · ${usd(standard.out)} output / 1M tokens`;
}

module.exports = {createIndex, references, rateSummary};
