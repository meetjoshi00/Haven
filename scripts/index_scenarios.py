"""
Upsert changed scenario files to Supabase pgvector.

Reads all content/scenarios/*.md, extracts frontmatter, embeds
title + domain + tags + skills_primary with all-MiniLM-L6-v2,
and upserts to Supabase only when version has changed.

Usage:
    python scripts/index_scenarios.py          # upsert changed
    python scripts/index_scenarios.py --dry-run  # parse only, no DB writes
"""
import argparse
import os
import sys
from pathlib import Path

import frontmatter  # python-frontmatter
import yaml
from dotenv import load_dotenv

load_dotenv()

SCENARIOS_DIR = Path(__file__).parent.parent / "content" / "scenarios"
MODEL_NAME = "all-MiniLM-L6-v2"


def build_embed_text(meta: dict) -> str:
    parts = [
        meta.get("title", ""),
        meta.get("domain", ""),
        " ".join(meta.get("skills_primary", [])),
        " ".join(meta.get("tags", [])),
    ]
    return " ".join(p for p in parts if p)


def load_scenarios() -> list[tuple[dict, str]]:
    results = []
    for path in sorted(SCENARIOS_DIR.glob("*.md")):
        post = frontmatter.load(str(path))
        results.append((dict(post.metadata), str(path)))
    return results


def main(dry_run: bool = False) -> None:
    scenarios = load_scenarios()
    if not scenarios:
        print("No scenario files found.")
        sys.exit(0)

    print(f"Found {len(scenarios)} scenario(s).")

    if dry_run:
        for meta, path in scenarios:
            embed_text = build_embed_text(meta)
            print(f"  {meta.get('id')} v{meta.get('version')} — '{embed_text[:60]}...'")
        print("Dry run complete. No DB writes.")
        return

    url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        print("ERROR: NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set.")
        sys.exit(1)

    from sentence_transformers import SentenceTransformer  # type: ignore
    from supabase import create_client  # type: ignore

    client = create_client(url, key)
    model = SentenceTransformer(MODEL_NAME)

    upserted = 0
    skipped = 0

    for meta, path in scenarios:
        scenario_id = meta.get("id")
        version = meta.get("version", 1)

        # Check existing version in DB
        existing = (
            client.table("scenarios")
            .select("version")
            .eq("scenario_id", scenario_id)
            .execute()
        )
        if existing.data and existing.data[0]["version"] == version:
            skipped += 1
            continue

        embed_text = build_embed_text(meta)
        embedding = model.encode(embed_text).tolist()

        client.table("scenarios").upsert(
            {
                "scenario_id": scenario_id,
                "version": version,
                "embedding": embedding,
                "metadata": {
                    k: meta[k]
                    for k in (
                        "title", "domain", "subdomain", "difficulty",
                        "skills_primary", "skills_secondary", "tags",
                        "estimated_turns", "reviewed", "rubric", "persona",
                        "recommended_next",
                    )
                    if k in meta
                },
            },
            on_conflict="scenario_id",
        ).execute()

        print(f"  Upserted {scenario_id} v{version}")
        upserted += 1

    print(f"Done. {upserted} upserted, {skipped} unchanged.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
