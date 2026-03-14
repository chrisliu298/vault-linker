# Vault Linker

**A skill for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [Codex](https://github.com/openai/codex) that systematically adds wikilinks across an entire Obsidian vault using parallel agents.**

> *Notes mention the same concepts but never link to each other. Vault Linker reads every note, finds the missing connections, and weaves them in — inline wikilinks, Related sections, bidirectional links, aliases — all at once.*

Vault Linker spawns 8 parallel agents, each processing a batch of topically related notes. Agents propose inline wikilinks, `## Related` entries, and frontmatter aliases. A programmatic validation pass filters out bad proposals (broken targets, self-links, duplicates, low-confidence matches), then a single apply step writes the changes. The result is a denser, more navigable link graph without creating new notes or deleting anything.

Invoke with `/vault-linker` or ask your agent to "link the vault", "build connections", "add wikilinks across notes", or "connect my notes".

## Table of Contents

- [How It Works](#how-it-works)
- [What It Does](#what-it-does)
- [Installation](#installation)
- [Usage](#usage)
- [Key Constraints](#key-constraints)
- [Files](#files)
- [Contributors](#contributors)

---

## How It Works

```
┌──────────────────────────────────────────────────────────────┐
│  1. Index: build_index.py → vault-index.json + lookup table  │
├──────────────────────────────────────────────────────────────┤
│  2. Batch: divide notes into ~8 groups of ≤30, by topic      │
├──────┬──────┬──────┬──────┬──────┬──────┬──────┬─────────────┤
│  A1  │  A2  │  A3  │  A4  │  A5  │  A6  │  A7  │     A8      │
│  ≤30 │  ≤30 │  ≤30 │  ≤30 │  ≤30 │  ≤30 │  ≤30 │     ≤30     │
├──────┴──────┴──────┴──────┴──────┴──────┴──────┴─────────────┤
│  3. Normalize: fix non-standard JSON output formats           │
├──────────────────────────────────────────────────────────────┤
│  4. Validate: programmatic checks on all proposals            │
├──────────────────────────────────────────────────────────────┤
│  5. Apply: text-matching insertion of links + aliases         │
├──────────────────────────────────────────────────────────────┤
│  6. Changelog: stats, per-note changes, isolated notes        │
└──────────────────────────────────────────────────────────────┘
```

The index script (`scripts/build_index.py`) scans every markdown file with YAML frontmatter, extracting note names, aliases, tags, existing wikilinks, and Related entries. A lookup table maps every linkable term (full names, explicit aliases, inferred acronyms) to its canonical note.

Eight standalone agents run in parallel, each reading all its assigned notes before proposing changes. After all agents finish, a normalization pass handles the ~40% of agents that produce non-standard JSON despite explicit format instructions. A validation script then checks every proposal against structural rules before anything is written to disk.

---

## What It Does

**Inline wikilinks** — scans body text for mentions of note names, aliases, or inferred acronyms that are not already linked. Links the first occurrence per section. Conservative: skips ambiguous terms, common English words used generically, and anything inside math blocks, code blocks, headings, or existing links.

**Related sections** — proposes additions to `## Related` based on shared tags (2+ `keyword/` tags in common), frequently co-linked notes (inline-linked 2+ times), and bidirectional enforcement (if A lists B, B should list A). Respects a soft cap of ~10 entries.

**Alias additions** — for notes with empty `aliases: []` whose title has a well-known, unambiguous acronym in the ML/RL/LLM domain, proposes adding it to frontmatter.

---

## Installation

Clone into your agent's skills directory:

**Claude Code:**

```bash
git clone https://github.com/chrisliu298/vault-linker.git ~/.claude/skills/vault-linker
```

**Codex:**

```bash
git clone https://github.com/chrisliu298/vault-linker.git ~/.codex/skills/vault-linker
```

---

## Usage

Point the agent at your vault:

> "Link my vault at ~/notes"

> "Run vault-linker on ~/obsidian-vault"

> "Add wikilinks across all my notes"

Or invoke directly with `/vault-linker`.

The skill will index the vault, spawn parallel agents, validate proposals, apply changes, and produce a changelog at `<vault_path>/vault-linker-changelog.md` with stats, per-note changes, most-linked notes, and remaining isolated notes.

---

## Key Constraints

- **Never creates new notes** — only links to existing ones
- **Never deletes content** — only adds wikilinks, Related entries, and aliases
- **Conservative** — when uncertain, skip; false positives are worse than false negatives
- **Idempotent** — running twice does not add duplicate links
- **Batch size cap** — 30 notes per agent to avoid context limits
- **Text matching** — uses the `original` field for applying changes, not line numbers (agents produce unreliable line numbers)
- **Standalone agents** — uses `Task` with `run_in_background`, not `TeamCreate` (team agents go idle between turns)

---

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Full skill definition: all 6 phases and linking rules |
| `scripts/build_index.py` | Vault indexer — extracts notes, aliases, tags, links into JSON |

---

## Contributors

- [@chrisliu298](https://github.com/chrisliu298)
- **Claude Code** — skill design, linking rules, and validation pipeline
