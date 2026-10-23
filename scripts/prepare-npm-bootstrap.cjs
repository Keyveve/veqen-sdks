// Build the initial candidate in GitHub Actions, retaining npm's signed
// provenance so an owner can publish this exact tarball after interactive 2FA.
const { execFileSync } = require('node:child_process');
const { createHash } = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

async function main() {
  if (process.env.GITHUB_ACTIONS !== 'true') throw new Error('GitHub Actions is required');
  const manifest = JSON.parse(fs.readFileSync('package.json', 'utf8'));
  if (manifest.name !== 'veqen' || manifest.version !== process.env.RELEASE_VERSION || !manifest.version.endsWith('-rc.0')) {
    throw new Error('Only the reviewed bootstrap candidate can be prepared');
  }
  const globalRoot = execFileSync('npm', ['root', '--global'], { encoding: 'utf8' }).trim();
  // The workflow pins npm because these are npm's internal provenance helpers.
  const dependencies = path.join(globalRoot, 'npm', 'node_modules');
  const { generateProvenance, verifyProvenance } = require(path.join(dependencies, 'libnpmpublish/lib/provenance.js'));
  const npa = require(path.join(dependencies, 'npm-package-arg'));
  const [packed] = JSON.parse(execFileSync('npm', ['pack', '--json', '--ignore-scripts'], { encoding: 'utf8' }));
  const subject = {
    name: npa.toPurl(npa.resolve(manifest.name, manifest.version)),
    digest: { sha512: createHash('sha512').update(fs.readFileSync(packed.filename)).digest('hex') },
  };
  const bundlePath = packed.filename + '.sigstore.json';
  const bundle = await generateProvenance([subject], {});
  fs.writeFileSync(bundlePath, JSON.stringify(bundle));
  await verifyProvenance(subject, bundlePath);
  console.log(JSON.stringify({ package: packed.filename, sha512: subject.digest.sha512, provenanceVerified: true }));
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
