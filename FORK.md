# seo-kit: Modeinspect fork of claude-blog

This repository is a fork of [AgriciDaniel/claude-blog](https://github.com/AgriciDaniel/claude-blog)
(remote `upstream`) carrying Modeinspect's additions on top. It is the single
source of truth for the blog skills, agents, and scripts used on every
Modeinspect site and in remote jobs. Never edit the installed copies in
`~/.claude` directly; change them here and reinstall.

## What the fork adds

| Area | Files | Purpose |
|---|---|---|
| Project content strategy | `scripts/validate_content_strategy.py`, `skills/blog/references/content-strategy.md` | A site repo keeps all blog-agent context under `seo-strategy/` (`site.json`, one `cluster-<slug>/cluster-plan.json` per topic cluster, briefs, drafts, `BRAND.md`/`VOICE.md`/`DISCOURSE.md`). The validator checks every plan and resolves one post's keywords, template, gate, and links. |
| Strategy-aware skills | `skills/blog`, `blog-write`, `blog-rewrite`, `blog-brief`, `blog-cluster`, `blog-brand`, `blog-discourse`, `blog-style`, `agents/blog-seo.md` | Write, rewrite, brief, and cluster look the post up in the strategy before doing their own keyword work; brand, style, and discourse read and write under `seo-strategy/`. |
| OpenAI image generation | `skills/blog-openai-image/` | Hero images, illustrations, and concept or process diagrams through the OpenAI Images API with a generate, view, re-prompt loop. `scripts/generate.mjs` (Node, no dependencies) loads `.env` from the working directory. Number-driven charts stay on `blog-chart`. |

## Install

Local machine (installs into `~/.claude` and writes `~/.claude/claude-blog-manifest.txt`):

```bash
git clone git@github.com:modeinspect/seo-kit.git
cd seo-kit && ./install.sh
```

Anything that must be reproducible (a remote job, a sandbox) pins a tag:

```bash
git clone --branch v1.0.0 --depth 1 git@github.com:modeinspect/seo-kit.git && ./seo-kit/install.sh
```

`uninstall.sh` removes everything the manifest lists.

Keys are read from the environment, or from `.env` in the directory a script
runs from (`OPENAI_API_KEY` for `blog-openai-image`). Site repos keep `.env`
gitignored; remote environments set the variables directly.

## Versioning

Tag every change a consumer can notice (`vMAJOR.MINOR.PATCH`). Consumers pin
tags, never `main`. Upstream's own version (`.claude-plugin/plugin.json`,
`CHANGELOG.md`) is left as upstream sets it.

## Updating from upstream

```bash
git fetch upstream
git merge upstream/main
/tmp/venv/bin/python -m pytest tests -q   # see below
```

Resolve conflicts in the files listed above. Upstream releases usually bump
the sub-skill and reference counts asserted by the tests
(`skills/blog/SKILL.md`, `CLAUDE.md`, `docs/ARCHITECTURE.md`); the fork adds one
sub-skill and one reference on top of upstream's numbers.

## Tests

```bash
python3 -m venv /tmp/venv && /tmp/venv/bin/pip install pytest -r requirements.txt
/tmp/venv/bin/python -m pytest tests -q
```

Known upstream failures without optional dependencies or network fixtures:
`test_markdown_body_html_is_sanitized`,
`test_fit_image_bytes_enforces_requested_dimensions`,
`test_pagespeed_response_populates_audit_details`, and the
`test_google_search_behavior.py` errors. Everything else must pass.
