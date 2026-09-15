---
name: blog-openai-image
description: >
  Generate a raster image asset (hero or cover image, OG image, illustration,
  concept or process diagram) with the OpenAI Images API. Runs a
  generate, view, re-prompt loop until the image passes review. Use when a blog
  post or page needs a generated image or diagram, or when the user says
  "generate an image", "make a diagram image", "hero image", "illustration",
  "openai image". Not for charts that encode numbers or for product screenshots.
argument-hint: "<what the image should show and where it goes>"
---

# OpenAI Image

Generates one image per call through `scripts/generate.mjs` (Node, no
dependencies). You write the prompt, run the script, look at the result with
Read, and re-prompt until it passes the review checklist.

## When to use it

| Asset | Use |
|---|---|
| Hero or cover image, OG image | This skill |
| Illustration or conceptual visual | This skill |
| Process, flow, or concept diagram with a few short labels | This skill |
| Chart that encodes numbers (bars, lines, percentages) | `blog-chart` SVG, so values stay exact |
| The real product UI | A real screenshot. Generated UI misrepresents the product |
| Third-party logos | Don't generate them |

## Setup

Run the script from the project root. It loads `.env` from the current
directory, then reads `OPENAI_API_KEY`; a variable already set in the
environment wins over the file. Check before starting:

```bash
cd <project-root> && node "$HOME/.claude/skills/blog-openai-image/scripts/generate.mjs" --check
```

The shell's working directory can reset between commands, so always put the
`cd` in the same command as the script.

It exits 0 and names the key's source when a key is available, and exits 1
otherwise. It never calls the API.

On exit 1, stop and tell the user to add `OPENAI_API_KEY=...` to `.env` at the
project root, and to confirm `git check-ignore .env` reports it as ignored.
Never ask for the key in chat, and never switch to a different image generator
instead.

Models: `gpt-image-2.5-sunburst` (default, most detailed) and
`gpt-image-2.5-flare` (faster; pass `--model gpt-image-2.5-flare` for quick
exploration before a final render).

## The loop

### 1. Brief

Decide, before writing any prompt:
- **Purpose and placement:** what the reader should understand, and where the
  image sits (hero, inline after which heading).
- **Size:** hero or inline landscape `1536x1024`, square `1024x1024`, tall
  `1024x1536`. For a 1200x630 hero or OG image, generate `1216x640` and resize
  with `sips --resampleHeightWidth 630 1200 <file>`. Custom sizes must be
  multiples of 16.
- **Style:** look at one or two existing images on the site with Read (for a
  blog post, images the project's posts already use) and at
  `seo-strategy/BRAND.md` if present. Describe palette (hex values), background,
  line weight, corner radius, and typography in the prompt so assets look like
  one family.
- **Exact text:** list every label the image must contain. Keep labels short
  and few. Text placement is the model's weakest point.

### 2. Prompt

Write the prompt to a file in the working folder:
`<folder>/assets/<name>-v1.prompt.md` (for a blog post, `<folder>` is its draft
folder). Structure:

1. **Subject and purpose:** one sentence.
2. **Layout:** composition, order, direction of flow, what is emphasized.
3. **Text:** every label in double quotes, in reading order, "and no other
   text".
4. **Style:** palette, background, flat or editorial, stroke and corner
   details, font style.
5. **Exclusions:** no logos, no watermark, no extra UI chrome, no decorative
   text.

### 3. Generate

Run with a long Bash timeout (`600000`); high-quality renders can take minutes:

```bash
cd <project-root> && node "$HOME/.claude/skills/blog-openai-image/scripts/generate.mjs" \
  --prompt-file <folder>/assets/<name>-v1.prompt.md \
  --out <folder>/assets/<name>-v1.png \
  --size 1536x1024 --quality high
```

Optional flags: `--model`, `--background transparent|opaque|auto`,
`--compression 0-100` (jpeg/webp only). The output format follows the `--out`
extension. The script refuses to overwrite a file; every attempt gets a new
`-vN` name. On an API error it exits 1 with the message; report it, don't retry
blindly.

### 4. Review

Read the image, then check each item and write down every defect:

- [ ] Every required label is present, spelled exactly, and legible at blog
      column width; there is no extra, garbled, or duplicated text
- [ ] Structure matches the brief: count of elements, order, arrow directions,
      emphasis
- [ ] Style matches the site's existing images (palette, background, weight)
- [ ] Nothing implies a product capability, customer, or metric that isn't true
- [ ] No logos, watermarks, or artifacts; edges and alignment are clean
- [ ] Composition survives the target crop or size

### 5. Re-prompt

If anything fails, write `<name>-v(N+1).prompt.md`. Name each defect and the
fix precisely (for example: "the arrow between 'Mockups' and 'Code' points
left; it must point right"), keep everything that worked, and generate again.
Keep all attempts for comparison.

Stop after 4 attempts. Show the user the best version and its remaining
defects, and propose a concrete change: fewer labels, a simpler layout, or
moving exact text into the surrounding HTML or markdown.

### 6. Finalize

- Copy the passing version to where the project serves images (for this kind
  of site, the directory existing post image paths resolve to, e.g.
  `public/image/blog/<post-slug>-<name>.png`). Don't overwrite an existing
  asset without asking.
- Reference it with a full-sentence alt text that states what the image shows,
  including its labels when they carry meaning.
- Report the file path, model, size, number of attempts, and the final prompt
  file path.
