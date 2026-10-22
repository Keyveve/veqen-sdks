# Veqen AI cost review

A GitHub Action that comments on every pull request that changes an AI model, with the cost per 1,000 calls before and after, and the monthly impact at your production volume when you add a Veqen key. It can also fail the check when a model or API in the code is about to retire.

```yaml
name: AI cost review
on: pull_request
permissions:
  contents: read
  pull-requests: write
jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
        with: { fetch-depth: 0 }
      - uses: Keyveve/veqen-sdks/github-action@v1
        with:
          api-key: ${{ secrets.VEQEN_API_KEY }}   # optional
          fail-within-days: 30                    # optional
```

`fetch-depth: 0` is needed so the action can diff against the base branch. The key is optional; without it the review compares per-call prices. The monthly impact needs a key from a Pro or Team organization. Other inputs: `base` (the ref to compare against, default the pull request's base branch) and `github-token` (default the workflow token). Comments are posted only on `pull_request`; when a later push removes the model changes, the comment is updated to say so. Forks use the job summary when a write token is unavailable. Docs: https://veqen-app.com/docs/cli

Use `pull_request`, never `pull_request_target` with an untrusted checkout. The action rejects that privileged event, installs the published CLI into a fresh temporary directory with install scripts disabled, and disables external Git diff/text conversion programs. It does not execute the reviewed project's code or locally installed binaries.

This directory is the source; it's published from the public `Keyveve/veqen-sdks` repository and tagged `v1`.

The repository-root `action.yml` is the GitHub Marketplace entry point. The
`github-action/action.yml` entry remains available for existing subdirectory
references. Keep both manifests in sync when changing the Action.
