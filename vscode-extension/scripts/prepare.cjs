const fs = require('node:fs');
const path = require('node:path');
const root = path.join(__dirname, '..');
fs.mkdirSync(path.join(root, 'data'), {recursive:true});
fs.copyFileSync(path.join(root, '../python/veqen/data/prices.json'), path.join(root, 'data/prices.json'));
fs.copyFileSync(path.join(root, '../python/THIRD_PARTY_NOTICES'), path.join(root, 'THIRD_PARTY_NOTICES'));
fs.copyFileSync(path.join(root, '../LICENSE'), path.join(root, 'LICENSE'));
console.log('Bundled the repository price snapshot and its license notices.');
