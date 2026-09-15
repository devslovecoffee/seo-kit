# Project Content Strategy (`seo-strategy/`)

A repo can hold all blog-agent context in one top-level directory. When
`<project-root>/seo-strategy/` exists, skills read and write their context there
and nowhere else. The project root is the site repository root. When the
directory does not exist, skills behave as before.

```
seo-strategy/
├── site.json                          # content_dir + url_pattern, shared by all clusters
├── BRAND.md, VOICE.md, DISCOURSE.md   # optional; /blog brand, /blog style, /blog discourse
├── cluster-<slug>/                    # one per topic cluster (pillar + spokes)
│   ├── cluster-plan.json              # status: active | draft
│   ├── cluster-map.html               # /blog cluster plan
│   └── cluster-scorecard.md           # /blog cluster execute
├── briefs/<post-slug>-brief.md        # /blog brief
└── drafts/<post-slug>/                # delivery-contract draft folders (write, rewrite, execute)
```

Posts never live in `seo-strategy/`. They go to `site.json` `content_dir`, or to
an entry's `file`.

## How the pieces fit

- A **cluster** is one pillar plus its spokes, grouped into sub-clusters by
  intent. A repo has as many clusters as it has topic hubs.
- An **active** cluster drives writing: write, rewrite, brief, and execute use
  its entries. A **draft** cluster is a proposal. Lookups report it (exit 4) and
  execute refuses it until the user sets `"status": "active"`.
- Keyword, slug, file, and URL uniqueness is checked across **all** clusters,
  drafts included, so a new cluster cannot cannibalize an existing one.
- A post is **published** when its target file exists, and **planned**
  otherwise. There is no per-post status field.

## Files

### `site.json`

```json
{ "content_dir": "content/blog", "url_pattern": "/blog/{slug}" }
```

### `cluster-<slug>/cluster-plan.json`

The directory slug is the cluster's id (lowercase, hyphenated; conventionally
the seed keyword). The plan uses the `cluster-plan.json` schema from
`skills/blog-cluster/SKILL.md` plus:

| Field | Level | Required | Meaning |
|---|---|---|---|
| `status` | plan | yes | `active` or `draft` |
| `slug` | post | yes | Filename stem and URL slug; for a published post, its existing slug |
| `file` | post | no | Repo-relative source when the page lives outside `content_dir` |
| `url` | post | no | Public URL when it does not follow `url_pattern` (pair with `file`) |
| `publish_order` | plan | no | Local post ids in execution order |
| `gate` | post | no | Editorial precondition, e.g. "no unscoped superiority claims" |
| `notes`, `source_assets` | post/plan | no | Context for the writer |
| `audience` | sub-cluster | no | Who the sub-cluster serves |

`template` must name a file in `skills/blog/templates/`. In `links_to` and
`links_from`, a bare id (`B3`) means this cluster, and `<cluster-slug>:<id>`
(`design-engineering:C4`) means another cluster. `links_to` is authoritative;
`links_from` is optional and informational. Do not put `content_dir` or
`url_pattern` in a plan.

## Validate and look up

Run from the project root with the trusted install path. Stop on errors and
show the output to the user:

```bash
BLOG_SCRIPT_DIR="${CLAUDE_BLOG_SCRIPTS_DIR:-$HOME/.claude/scripts}"
python3 "$BLOG_SCRIPT_DIR/validate_content_strategy.py"                       # everything
python3 "$BLOG_SCRIPT_DIR/validate_content_strategy.py" --post <query> --json # one post
```

`<query>` is `<cluster-slug>:<id>`, an id that is unique across clusters, a
slug, a target file path, a title, or a primary keyword.

| Exit | Meaning | Action |
|---|---|---|
| 0 | Valid; `post` holds the resolved context | Proceed. Show warnings to the user once |
| 1 | Validation errors (any file) | Stop. Show errors; do not write or rewrite until fixed |
| 2 | No `seo-strategy/` directory | No strategy: behave as before |
| 3 | No entry, or several, match | Say the post is off-strategy (or list the matches). Ask whether to add or pick an entry, or proceed off-strategy |
| 4 | Match is in a draft cluster | Say so. Ask whether to activate the cluster or proceed against the draft entry |

The `post` object has `ref`, `cluster_slug`, `cluster_status`, `plan`, `role`
(pillar or supporting), `seed_keyword`, `group`, `title`, `primary_keyword`,
`secondary_keywords`, `template`, `word_count_target`, `slug`, `url`, `file`,
`exists`, and `pillar`. It also has `links_to` and `links_from`, each link
resolved to `ref`, `title`, `primary_keyword`, `url`, `file`, `exists`, and
cluster status. It includes `gate`, `notes`, and `source_assets` when set.

## Using a post context

1. **Targeting.** Build the `=== CLUSTER CONTEXT ===` block from
   `skills/blog-cluster/references/execution-workflow.md` using the post
   context. It replaces keyword and template questions and template
   auto-detection.
2. **Internal links.** For each `links_to` entry with `exists: true`, link its
   `url` (root-relative). For `exists: false`, insert
   `[INTERNAL-LINK: <anchor> -> <url>]`. `/blog cluster execute` or a later
   rewrite resolves it once the target exists.
3. **Gate and notes.** Pass `gate` to `blog-writer` and `blog-reviewer` as a hard
   editorial constraint, and repeat it in the delivery summary so the user
   confirms it before publishing. Pass `notes` and `source_assets` to the
   writer. When a source asset names a site page (e.g. `/design-qa page`), read
   that page's source in the repo.
4. **Validation agents.** Pass `primary_keyword`, `secondary_keywords`, `slug`,
   and `url` to `blog-seo` and `blog-reviewer` so they check against the target.
5. **Files.** Use `seo-strategy/drafts/<slug>/` as the delivery-contract draft
   folder. After all gates pass, write the final markdown to the target file,
   using the frontmatter field names of existing files in the same directory.
   Put the hero where existing posts' image paths resolve (e.g.
   `image: /image/blog/<slug>.png` means `public/image/blog/`). Do not copy
   `.html`, `.pdf`, or `preview/` into the content directory.
6. **Never change a published slug, file, or URL** during a rewrite.

## Brand, voice, and discourse context

With `seo-strategy/` present, `BRAND.md`, `VOICE.md`, and `DISCOURSE.md` live at
`seo-strategy/<name>`. Load them with the trusted helper by passing that path
(`python3 "$HELPER" seo-strategy/BRAND.md`); the untrusted-data contract in
`skills/blog/SKILL.md` still applies. Root-level copies are ignored, and the
validator warns when it finds one.

## Adding or adjusting clusters

- **New cluster:** `/blog cluster plan <seed>` writes
  `seo-strategy/cluster-<seed-slug>/cluster-plan.json` with `"status": "draft"`
  and its `cluster-map.html`. Set `"status": "active"` when the user approves
  the plan.
- **Re-plan an existing cluster** (`/blog cluster plan <seed>` or
  `--from strategy`, matching an existing directory): update its plan in place.
  1. Produce the proposed plan in memory.
  2. Show a change summary: entries added and removed, and changed primary
     keywords, templates, slugs, and links. Refuse to change the slug, `file`,
     or `url` of a published entry unless the user explicitly asks (that needs
     a redirect).
  3. Keep user-authored fields the plan phase does not produce (`status`,
     `notes`, `gate`, `source_assets`, `audience`, `publish_order`, `file`,
     `url`).
  4. After approval, write the file, update `generated_at`, and run the
     validator. Fix any errors before reporting done.
- **Move a post between clusters:** remove the entry from one plan, add it to
  the other with the same `slug`, and update any `<cluster>:<id>` links that
  pointed at it. The validator reports dangling links.
- **Small edits** (one post, a link, a keyword): edit the plan directly, then run
  the validator.
