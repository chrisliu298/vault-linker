---
name: vault-linker
user-invocable: true
description: >
  Build connections across an entire Obsidian vault using a large team of parallel agents.
  Adds inline wikilinks where concepts are mentioned but not linked, populates ## Related
  sections with missing connections, enforces bidirectional Related links, adds missing
  frontmatter aliases, and auto-reviews via two independent reviewer agents. Use when asked
  to "link the vault", "build connections", "add wikilinks across notes", "connect my notes",
  or any request to improve the link graph of an Obsidian vault. Invoke with /vault-linker.
effort: high
---

# Vault Linker

Coordinate 8 parallel standalone linker agents to systematically add wikilinks across an Obsidian vault — both inline (within body text) and in `## Related` sections. Validate proposals programmatically, then apply.

## Phase 1: Build the Index and Lookup Table

Run the index script:

```bash
python3 <skill_path>/scripts/build_index.py <vault_path> /tmp/vault-index.json
```

Read `/tmp/vault-index.json`. This is the **source of truth** for what notes exist.

**Scope**: Only process notes that have YAML frontmatter (skip utility files like NOTES.md, TODOs.md, CLAUDE.md, LLM Resources.md).

Build a **lookup table** — a map from every linkable term to its canonical note name:
- Full note name → itself (e.g., `"Proximal Policy Optimization"`)
- Each explicit alias from `aliases:` → note name (e.g., `"PPO"` → `"Proximal Policy Optimization"`)
- **Inferred acronyms**: For multi-word note titles, auto-generate the obvious acronym and add it to the lookup. E.g., `"GAE"` → `"Generalized Advantage Estimation"`, `"RoPE"` → `"Rotary Position Embedding"`, `"MoE"` → `"Mixture of Experts"`. Only include acronyms that are unambiguous (one note matches). If two notes produce the same acronym, exclude it from the lookup.

Save the lookup table to `/tmp/vault-linker/lookup.json`.

## Phase 2: Spawn Standalone Linker Agents

**Do NOT use TeamCreate/teammates** — use standalone `Task` agents with `run_in_background: true`. Team agents go idle between turns and require manual wake-up messages, making them far too slow for this workload.

**Batching**: Divide notes into ~8 batches of **≤30 notes each**, grouped by topic (shared `area/` or `keyword/` tags) so each agent has domain context. **Never exceed 30 notes per batch** — larger batches cause agents to hit context limits and fail to produce output.

Spawn all 8 agents in parallel using `Task` with `run_in_background: true`, `mode: "bypassPermissions"`, and `model: "sonnet"`. Each agent's prompt must include:
1. The exact list of note filenames to process
2. The vault path and paths to lookup table (`/tmp/vault-linker/lookup.json`) and index (`/tmp/vault-index.json`)
3. A copy of the linking rules from Phase 3 below
4. Instruction to write proposed changes to `/tmp/vault-linker/batch-{N}.json`

**Critical — enforce output format**: The prompt must explicitly state:
> The top-level keys MUST be note names mapping to objects with `inline_additions`, `related_additions`, `alias_additions`. Do NOT wrap in `{"batch": N, "notes": [...]}` or any other envelope. Only include notes with at least one proposed change.

And include this exact example:
```json
{
  "Note Name": {
    "inline_additions": [
      {"original": "MLA stores a compressed", "replacement": "[[Multi-Head Latent Attention|MLA]] stores a compressed", "confidence": "high"}
    ],
    "related_additions": ["Attention Variants", "Rotary Position Embedding"],
    "alias_additions": ["FMT"]
  }
}
```

**Do not include `line` numbers in the format** — agents produce unreliable line numbers. Use text matching (`original` field) for applying changes instead.

**Processing mode**: Each agent reads ALL its assigned notes first to build full context, then produces proposed changes for all of them. Do not interleave reading and editing.

### Output Normalization

After all agents complete, run a normalization pass on each batch file. Agents sometimes produce non-standard formats despite explicit instructions. Write a Python script that:
1. Detects the format (standard vs envelope vs list-of-objects)
2. Converts to the standard `{"Note Name": {"inline_additions": [...], ...}}` format
3. Overwrites the batch file with the normalized version
4. Reports stats (notes with changes, inline/related/alias counts)

## Phase 3: Linker Agent Rules

Each agent reads its assigned notes and proposes changes following these rules. **Do NOT edit files directly** — write proposals to the batch JSON file.

### Inline Wikilinks

Scan body text (after frontmatter, before `## Related`) for mentions of note names or aliases that are NOT already wikilinked.

**Add a wikilink when:**
- A concept name matches a note name, alias, or inferred acronym from the lookup table
- The mention is in prose text, not inside a protected context (see below)
- The concept is **substantively discussed or referenced** — not a passing use of a common English word. E.g., link "PPO" when discussing the algorithm, not "inference" when used as a generic verb

**Conservative linking**: When uncertain whether a mention refers to the note, do NOT propose the link. False positives are worse than false negatives.

**Wikilink format:**
- Full name match: `[[Note Name]]`
- Alias/acronym match: `[[Full Note Name|displayed text]]` — preserve original casing
- Examples: `"PPO"` → `[[Proximal Policy Optimization|PPO]]`, `"GAE"` → `[[Generalized Advantage Estimation|GAE]]`

**Link frequency**: Link the **first occurrence per `##` section**. If "PPO" appears in 3 sections, propose 3 links.

**Do NOT link:**
- The note's own name or aliases (no self-links)
- Inside existing `[[...]]` wikilinks
- Inside `$...$` or `$$...$$` math blocks
- Inside code blocks (``` or inline `` ` ``)
- Inside URLs or markdown links `[text](url)`
- Inside headings (`#`, `##`, `###`)
- A target already linked earlier in the same `##` section
- Ambiguous terms that match multiple notes — skip entirely
- Common English words used generically (e.g., "Inference" as a verb, "Purpose" as a generic noun, "Scaling Law" when not referring to the specific note)
- Short inferred acronyms (2 letters) unless they are well-known domain-specific acronyms (PPO, GRPO, GAE, MoE, GQA, MLA, MTP, RoPE, etc.). Most 2-letter acronyms from auto-generation are ambiguous noise

**Confidence levels** for each proposal:
- **high**: Exact alias match or unambiguous full-name match in relevant context
- **medium**: Inferred acronym match or partial name match with supporting context
- **low**: Plausible but context-dependent; could be generic usage

### Related Section

After identifying inline links, propose additions to `## Related`:
- Notes sharing **2+ `keyword/` tags** with the current note, not already in Related
- Notes linked inline **2+ times** in the body but missing from Related
- **Bidirectional enforcement**: If note A has note B in Related (or will after this pass), propose adding A to B's Related too
- **Soft cap of ~10**: If a note already has 7+ Related entries, only propose additions with high confidence
- Keep all existing Related entries — never propose removal
- Format: `- [[Note Name]]` or `- [[Note Name|Display]]` if an alias is commonly used
- Sort the full list alphabetically after additions

### Alias Additions

For notes with `aliases: []` whose title has a well-known, unambiguous acronym (e.g., "Generalized Advantage Estimation" → GAE), propose adding it to `aliases:`.

Only propose acronyms that:
- Are commonly used in the vault's domain (ML/RL/LLM research)
- Map to exactly one note (no collisions)
- Are 2-5 characters long

### Protected Sections

Do NOT modify:
- `## References` sections
- Frontmatter fields other than `date-modified` and `aliases`

## Phase 4: Programmatic Validation

**Do NOT use reviewer agents** — they hit context limits trying to read 8 batch files + spot-check notes, and fail to produce output. Use a Python validation script instead.

Write and run a Python script that validates all proposals from all batch files:

### Validation checks for inline links:
1. **Link target exists**: Extract the note name from `[[...]]` in the replacement — it must exist in the vault index
2. **No self-links**: The target must not be the same as the source note
3. **Source note exists**: The source note must exist in the vault index
4. **Reject low confidence**: Skip any proposal with `confidence: "low"`
5. **Valid wikilink syntax**: The replacement must contain a `[[...]]` wikilink
6. **Not a no-op**: The `original` and `replacement` must differ
7. **Not already linked in file**: Read the actual note file and check if the target is already wikilinked somewhere in the body (the vault index may be stale). If `[[Target]]` or `[[Target|...]]` already appears in the body, skip the proposal

### Validation checks for related additions:
1. **Target exists**: The proposed related note must exist in the vault index
2. **Not already present**: Read the actual note's `## Related` section from the file (not just the index — it may be stale) and reject if already listed
3. **No self-links**: Cannot add a note to its own Related section
4. **Soft cap**: If a note already has 10+ related entries, reject the addition

### Validation checks for alias additions:
1. **Unambiguous**: The acronym must not collide with another note's acronym in the lookup table

Save validated proposals to `/tmp/vault-linker/validated-proposals.json` and print summary stats.

## Phase 5: Apply Changes

Apply all validated changes using a Python script:

1. For each note with validated changes, read the file
2. **Inline wikilinks**: Find the `original` text in the body (between frontmatter end and `## Related`/`## References`), verify it's not inside an existing `[[]]`, math block, code block, or heading, then replace the first valid occurrence with the `replacement` text. Use **text matching** (not line numbers — agents produce unreliable line numbers)
3. **Related section**: Parse existing `- [[...]]` entries, add new ones, sort alphabetically, rebuild the section
4. **Aliases**: Update `aliases: []` to include the new alias
5. **date-modified**: Update to current timestamp
6. Write the modified note

## Phase 6: Changelog and Summary

Write a changelog to `<vault_path>/vault-linker-changelog.md`:

```markdown
# Vault Linker Changelog — YYYY-MM-DD HH:MM

## Stats
- Notes analyzed: N
- Notes modified: N
- Inline wikilinks added: N
- Related entries added: N
- Aliases added: N
- Proposals skipped (reviewer conflict): N

## Changes by Note
### Note Name
- Inline: "PPO" → [[Proximal Policy Optimization|PPO]] (L44)
- Related: +[[Importance Sampling]], +[[KL Penalty Patterns]]
- Alias: +PPO
...

## Top 10 Most-Linked-To Notes
1. Note Name (N incoming links)
...

## Remaining Isolated Notes
- Note Name (0 incoming + 0 outgoing)
...
```

Print a concise summary to the terminal.

## Important Constraints

- **Never create new notes** — only link to existing ones
- **Never delete content** — only add wikilinks, Related entries, and aliases
- **Preserve formatting** — do not reflow paragraphs or change whitespace beyond the link insertion point
- **Conservative** — when uncertain, skip. Programmatic validation catches structural errors; agents are instructed to be conservative on semantic judgments
- **Batch by topic** — agents working on related notes process them together for domain context
- **Idempotent** — running the skill twice must not add duplicate links
- **≤30 notes per batch** — larger batches cause agents to hit context limits and fail silently
- **Standalone agents, not teammates** — use `Task` with `run_in_background: true`, not `TeamCreate`. Team agents go idle between turns and require manual wake-up, making them 5-10x slower
- **Text matching, not line numbers** — agents produce unreliable line numbers; always use the `original` field for text matching when applying changes
- **Normalize output formats** — despite explicit format instructions, ~40% of agents produce non-standard JSON envelopes; always run a normalization pass before validation
