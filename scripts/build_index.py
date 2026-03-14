#!/usr/bin/env python3
"""Build a JSON index of all notes in an Obsidian vault.

Output: JSON with note name, aliases, tags, existing wikilinks, and Related entries.
Usage: python build_index.py <vault_path> [output_path]

No external dependencies — stdlib only.
"""

import json
import os
import re
import sys


def parse_yaml_list(raw: str) -> list[str]:
    """Parse a simple YAML list (inline [...] or block - item)."""
    raw = raw.strip()
    if raw.startswith("["):
        items = raw.strip("[]").split(",")
        return [i.strip().strip("'\"") for i in items if i.strip().strip("'\"")]
    return re.findall(r"^\s*-\s+(.+)$", raw, re.MULTILINE)


def extract_frontmatter(content: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return {}
    fm_text = m.group(1)
    result = {}

    # Extract aliases
    am = re.search(r"^aliases:\s*(.*?)(?=^\w|\Z)", fm_text, re.MULTILINE | re.DOTALL)
    if am:
        result["aliases"] = parse_yaml_list(am.group(1))

    # Extract tags
    tm = re.search(r"^tags:\s*(.*?)(?=^\w|\Z)", fm_text, re.MULTILINE | re.DOTALL)
    if tm:
        result["tags"] = parse_yaml_list(tm.group(1))

    return result


def extract_wikilinks(text: str) -> list[str]:
    """Extract all wikilink targets from text (not embeds)."""
    return re.findall(r"(?<!!)\[\[([^\]|]+?)(?:\|[^\]]+?)?\]\]", text)


def extract_related_links(content: str) -> list[str]:
    """Extract wikilinks from the ## Related section only."""
    m = re.search(r"^## Related\s*\n(.*?)(?=^## |\Z)", content, re.MULTILINE | re.DOTALL)
    if not m:
        return []
    return extract_wikilinks(m.group(1))


def extract_body(content: str) -> str:
    """Get content after frontmatter."""
    m = re.match(r"^---\n.*?\n---\n?", content, re.DOTALL)
    return content[m.end():] if m else content


def build_index(vault_path: str) -> dict:
    index = {}
    for fname in sorted(os.listdir(vault_path)):
        if not fname.endswith(".md"):
            continue
        note_name = fname[:-3]
        fpath = os.path.join(vault_path, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            continue

        fm = extract_frontmatter(content)
        body = extract_body(content)
        aliases = fm.get("aliases", [])
        tags = fm.get("tags", [])

        # Inline wikilinks (excluding Related/References sections)
        related_section_start = re.search(r"^## Related", body, re.MULTILINE)
        body_before_related = body[:related_section_start.start()] if related_section_start else body
        inline_links = extract_wikilinks(body_before_related)
        related_links = extract_related_links(content)

        index[note_name] = {
            "aliases": aliases,
            "tags": tags,
            "inline_links": sorted(set(inline_links)),
            "related_links": sorted(set(related_links)),
        }

    return index


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: build_index.py <vault_path> [output_path]", file=sys.stderr)
        sys.exit(1)

    vault_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(vault_path, ".vault-index.json")

    index = build_index(vault_path)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    print(f"Indexed {len(index)} notes → {output_path}")
