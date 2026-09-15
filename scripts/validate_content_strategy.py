#!/usr/bin/env python3
"""Validate a repo's blog content strategy and look up one post's targeting.

Layout, all under `<project-root>/seo-strategy/`:
    site.json                          {"content_dir": "...", "url_pattern": ".../{slug}"}
    cluster-<slug>/cluster-plan.json   one hub-and-spoke cluster per directory

Each plan uses the blog-cluster `cluster-plan.json` schema plus the fields in
`skills/blog/references/content-strategy.md`: top-level `status` (active or
draft), per-post `slug`, optional `file` / `url` / `publish_order`, and
cross-cluster links written as `<cluster-slug>:<id>`.

Usage:
    python3 validate_content_strategy.py [--root DIR] [--json]
    python3 validate_content_strategy.py --post <query> [--root DIR] [--json]

<query> is `<cluster-slug>:<id>`, an id that is unique across clusters, a slug,
a target file path, a title, or a primary keyword.

Exit codes: 0 valid (warnings allowed), 1 validation errors, 2 no seo-strategy/
directory, 3 --post matched no entry or several, 4 --post matched an entry in a
draft cluster (the post context is still emitted).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

STRATEGY_DIR = "seo-strategy"
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "skills" / "blog" / "templates"
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CONTEXT_FILES = ("BRAND.md", "VOICE.md", "DISCOURSE.md")
STATUSES = ("active", "draft")

SITE_REQUIRED = {"content_dir": str, "url_pattern": str}
PLAN_REQUIRED = {"seed_keyword": str, "status": str, "pillar": dict, "clusters": list}
POST_REQUIRED = {
    "id": str,
    "title": str,
    "primary_keyword": str,
    "secondary_keywords": list,
    "template": str,
    "word_count_target": int,
    "slug": str,
    "links_to": list,
}


def check_fields(obj: dict, required: dict, where: str, errors: list[str]) -> bool:
    ok = True
    for field, kind in required.items():
        if field not in obj:
            errors.append(f"{where}: missing required field '{field}'")
            ok = False
        elif not isinstance(obj[field], kind):
            errors.append(f"{where}: '{field}' must be {kind.__name__}")
            ok = False
    return ok


def load_json(path: Path, rel: str, errors: list[str]) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        errors.append(f"{rel}: not valid JSON: {e}")
        return None
    if not isinstance(data, dict):
        errors.append(f"{rel}: must contain a JSON object")
        return None
    return data


def qualify(ref: str, cluster_slug: str) -> str:
    return ref if ":" in ref else f"{cluster_slug}:{ref}"


def target_file(post: dict, site: dict) -> str:
    return post.get("file") or f"{site['content_dir'].rstrip('/')}/{post['slug']}.md"


def target_url(post: dict, site: dict) -> str:
    return post.get("url") or site["url_pattern"].replace("{slug}", post["slug"])


def load_plans(root: Path, errors: list[str]) -> list[dict]:
    """Flatten every cluster plan into entries keyed `<cluster-slug>:<id>`."""
    entries = []
    paths = sorted((root / STRATEGY_DIR).glob("cluster-*/cluster-plan.json"))
    if not paths:
        errors.append(f"no {STRATEGY_DIR}/cluster-*/cluster-plan.json found")
    for path in paths:
        rel = path.relative_to(root).as_posix()
        cluster_slug = path.parent.name.removeprefix("cluster-")
        if not SLUG_RE.match(cluster_slug):
            errors.append(f"{rel}: directory must be cluster-<lowercase-hyphenated-slug>")
            continue
        plan = load_json(path, rel, errors)
        if plan is None or not check_fields(plan, PLAN_REQUIRED, rel, errors):
            continue
        for moved in ("content_dir", "url_pattern"):
            if moved in plan:
                errors.append(f"{rel}: '{moved}' belongs in {STRATEGY_DIR}/site.json")
        if plan["status"] not in STATUSES:
            errors.append(f"{rel}: status must be one of {list(STATUSES)}")
        base = {"cluster_slug": cluster_slug, "plan": rel, "plan_data": plan}
        if check_fields(plan["pillar"], POST_REQUIRED, f"{rel} pillar", errors):
            entries.append({**base, "post": plan["pillar"], "role": "pillar", "group": None})
        for gi, group in enumerate(plan["clusters"]):
            name = group.get("name", f"clusters[{gi}]")
            for pi, post in enumerate(group.get("posts", [])):
                where = f"{rel} {name} posts[{pi}] ({post.get('id', '?')})"
                if check_fields(post, POST_REQUIRED, where, errors):
                    entries.append({**base, "post": post, "role": "supporting", "group": group})
    for entry in entries:
        entry["key"] = f"{entry['cluster_slug']}:{entry['post']['id']}"
    return entries


def validate(root: Path) -> tuple[dict | None, list[dict], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    sdir = root / STRATEGY_DIR

    site = None
    site_rel = f"{STRATEGY_DIR}/site.json"
    if not (sdir / "site.json").is_file():
        errors.append(f"{site_rel} is missing")
    else:
        site = load_json(sdir / "site.json", site_rel, errors)
        if site is not None and check_fields(site, SITE_REQUIRED, site_rel, errors):
            if "{slug}" not in site["url_pattern"]:
                errors.append(f"{site_rel}: 'url_pattern' must contain '{{slug}}'")
            if not (root / site["content_dir"]).is_dir():
                errors.append(f"{site_rel}: content_dir '{site['content_dir']}' is not a directory")
    if not TEMPLATES_DIR.is_dir():
        errors.append(f"blog templates directory not found at {TEMPLATES_DIR}")
    templates = {p.stem for p in TEMPLATES_DIR.glob("*.md")}

    for name in CONTEXT_FILES:
        if (root / name).is_file():
            warnings.append(f"{name} at the project root is ignored; move it to {STRATEGY_DIR}/{name}")

    entries = load_plans(root, errors)
    if errors:
        return site, entries, errors, warnings

    by_key: dict[str, dict] = {}
    seen: dict[str, dict[str, str]] = {"slug": {}, "primary_keyword": {}, "file": {}, "url": {}}
    for entry in entries:
        post, key = entry["post"], entry["key"]
        if key in by_key:
            errors.append(f"{key}: duplicate id in {entry['plan']}")
        by_key[key] = entry
        if not SLUG_RE.match(post["slug"]):
            errors.append(f"{key}: slug '{post['slug']}' must be lowercase letters, numbers and hyphens")
        if post["template"] not in templates:
            errors.append(f"{key}: template '{post['template']}' is not one of: {', '.join(sorted(templates))}")
        if "file" in post:
            if Path(post["file"]).is_absolute():
                errors.append(f"{key}: file '{post['file']}' must be relative to the project root")
            elif not (root / post["file"]).is_file():
                errors.append(f"{key}: file '{post['file']}' does not exist")
        if "url" in post:
            if not post["url"].startswith("/"):
                errors.append(f"{key}: url '{post['url']}' must be root-relative (start with '/')")
            if "file" not in post:
                warnings.append(
                    f"{key}: url '{post['url']}' overrides url_pattern but the post lives in content_dir, "
                    f"which the site serves at url_pattern; add a route or set 'file' to the page's source"
                )
        values = {
            "slug": post["slug"],
            "primary_keyword": post["primary_keyword"].strip().lower(),
            "file": target_file(post, site),
            "url": target_url(post, site),
        }
        for kind, value in values.items():
            other = seen[kind].get(value)
            if other:
                errors.append(f"{key}: {kind} '{value}' already used by {other}")
            seen[kind][value] = key

    for entry in entries:
        post, key, cs = entry["post"], entry["key"], entry["cluster_slug"]
        for ref in post["links_to"]:
            target = qualify(ref, cs)
            if target not in by_key:
                errors.append(f"{key}: links_to unknown post '{ref}'")
            elif target == key:
                errors.append(f"{key}: links_to itself")
        for ref in post.get("links_from", []):
            if qualify(ref, cs) not in by_key:
                errors.append(f"{key}: links_from unknown post '{ref}'")

    for cs in sorted({e["cluster_slug"] for e in entries}):
        cluster_entries = [e for e in entries if e["cluster_slug"] == cs]
        plan = cluster_entries[0]["plan_data"]
        rel = cluster_entries[0]["plan"]
        order = plan.get("publish_order")
        if order is None:
            continue
        ids = {e["post"]["id"] for e in cluster_entries}
        unknown = [pid for pid in order if pid not in ids]
        dupes = sorted({pid for pid in order if order.count(pid) > 1})
        if unknown:
            errors.append(f"{rel}: publish_order has ids not in this cluster {unknown}")
        if dupes:
            errors.append(f"{rel}: publish_order has duplicate ids {dupes}")
        missing = sorted(ids - set(order))
        if missing:
            warnings.append(f"{rel}: publish_order does not list {missing}")

    if errors:
        return site, entries, errors, warnings

    edges = {(e["key"], qualify(t, e["cluster_slug"])) for e in entries for t in e["post"]["links_to"]}
    for entry in entries:
        post, key = entry["post"], entry["key"]
        if "links_from" in post:
            declared = {qualify(ref, entry["cluster_slug"]) for ref in post["links_from"]}
            actual = {s for s, t in edges if t == key}
            for source in sorted(declared - actual):
                warnings.append(f"{key}: links_from lists {source}, but {source}.links_to does not include it")
            # Incoming links from other clusters need not be mirrored in this plan.
            same_cluster = {s for s in actual if s.startswith(f"{entry['cluster_slug']}:")}
            for source in sorted(same_cluster - declared):
                warnings.append(f"{key}: {source}.links_to includes it, but links_from does not list {source}")
        if entry["role"] == "supporting":
            incoming = sum(1 for _, t in edges if t == key)
            if incoming < 2:
                warnings.append(f"{key}: {incoming} incoming link(s) from links_to; spokes need at least 2")

    primaries = {e["post"]["primary_keyword"].strip().lower(): e["key"] for e in entries}
    for entry in entries:
        for kw in entry["post"]["secondary_keywords"]:
            owner = primaries.get(kw.strip().lower())
            if owner and owner != entry["key"]:
                warnings.append(f"{entry['key']}: secondary keyword '{kw}' is the primary keyword of {owner}")

    mapped = {target_file(e["post"], site) for e in entries}
    for md in sorted((root / site["content_dir"]).glob("*.md")):
        rel = md.relative_to(root).as_posix()
        if rel not in mapped:
            warnings.append(f"off-strategy post (in no cluster): {rel}")

    return site, entries, errors, warnings


def resolve_link(entry: dict, site: dict, root: Path) -> dict:
    post = entry["post"]
    file = target_file(post, site)
    return {
        "ref": entry["key"],
        "cluster_slug": entry["cluster_slug"],
        "cluster_status": entry["plan_data"]["status"],
        "id": post["id"],
        "title": post["title"],
        "primary_keyword": post["primary_keyword"],
        "url": target_url(post, site),
        "file": file,
        "exists": (root / file).is_file(),
    }


def post_context(entry: dict, entries: list[dict], site: dict, root: Path) -> dict:
    post, key, cs = entry["post"], entry["key"], entry["cluster_slug"]
    by_key = {e["key"]: e for e in entries}
    pillar = next(e for e in entries if e["cluster_slug"] == cs and e["role"] == "pillar")
    group = entry["group"]
    context = {
        **resolve_link(entry, site, root),
        "plan": entry["plan"],
        "role": entry["role"],
        "seed_keyword": entry["plan_data"]["seed_keyword"],
        "group": None if group is None else {k: group[k] for k in ("name", "intent", "audience") if k in group},
        "secondary_keywords": post["secondary_keywords"],
        "template": post["template"],
        "word_count_target": post["word_count_target"],
        "slug": post["slug"],
        "pillar": resolve_link(pillar, site, root),
        "links_to": [resolve_link(by_key[qualify(t, cs)], site, root) for t in post["links_to"]],
        "links_from": [
            resolve_link(e, site, root)
            for e in entries
            if key in {qualify(t, e["cluster_slug"]) for t in e["post"]["links_to"]}
        ],
    }
    for passthrough in ("gate", "notes", "source_assets"):
        if passthrough in post:
            context[passthrough] = post[passthrough]
    return context


def find_entries(query: str, entries: list[dict], site: dict, root: Path) -> list[dict]:
    q = query.strip()
    if ":" in q:
        return [e for e in entries if e["key"] == q]
    path = Path(q)
    if path.is_absolute():
        try:
            rel = path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            rel = None
    else:
        rel = path.as_posix().removeprefix("./")
    return [
        e
        for e in entries
        if q in (e["post"]["id"], e["post"]["slug"])
        or rel == target_file(e["post"], site)
        or q.lower() in (e["post"]["title"].lower(), e["post"]["primary_keyword"].lower())
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", default=".", help="Project root containing seo-strategy/ (default: cwd)")
    parser.add_argument("--post", help="Look up one post: <cluster>:<id>, id, slug, target file, title or primary keyword")
    parser.add_argument("--json", action="store_true", help="Emit a JSON report")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not (root / STRATEGY_DIR).is_dir():
        print(f"Error: no {STRATEGY_DIR}/ directory in {root}", file=sys.stderr)
        return 2

    site, entries, errors, warnings = validate(root)
    report: dict = {"strategy_dir": str(root / STRATEGY_DIR), "errors": errors, "warnings": warnings}
    code = 1 if errors else 0

    if not errors:
        clusters = []
        for cs in sorted({e["cluster_slug"] for e in entries}):
            ce = [e for e in entries if e["cluster_slug"] == cs]
            published = sum(1 for e in ce if (root / target_file(e["post"], site)).is_file())
            clusters.append({
                "slug": cs,
                "status": ce[0]["plan_data"]["status"],
                "plan": ce[0]["plan"],
                "posts": len(ce),
                "published": published,
                "planned": len(ce) - published,
            })
        report["clusters"] = clusters

    if args.post and not errors:
        matches = find_entries(args.post, entries, site, root)
        if len(matches) == 1:
            report["post"] = post_context(matches[0], entries, site, root)
            if report["post"]["cluster_status"] == "draft":
                code = 4
        else:
            report["post_error"] = (
                f"no strategy entry matches '{args.post}'"
                if not matches
                else f"'{args.post}' matches several entries: {[m['key'] for m in matches]}"
            )
            code = 3

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return code

    print(f"Strategy: {report['strategy_dir']}")
    for c in report.get("clusters", []):
        print(f"  {c['slug']} [{c['status']}]: {c['posts']} posts ({c['published']} published, {c['planned']} planned)")
    for label, items in (("ERRORS", errors), ("WARNINGS", warnings)):
        if items:
            print(f"\n{label} ({len(items)}):")
            for item in items:
                print(f"  - {item}")
    if "post" in report:
        if code == 4:
            print(f"\nNote: {report['post']['ref']} is in a draft cluster")
        print("\nPost context:")
        print(json.dumps(report["post"], indent=2, ensure_ascii=False))
    if "post_error" in report:
        print(f"\nError: {report['post_error']}", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
