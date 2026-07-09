# Reports Repo Convention

Public reports repo. **Every AI agent MUST read and follow this file before creating, moving, renaming, or committing anything.** When in doubt, ask — do not act.

**Repo:** `https://github.com/Xyz9Selu/reports`

---

## 1. Structure

Path depth ≤ 3 levels: `root / <domain> / <topic>`. The leaf (`<topic>`) holds every version of one report and all its assets. Intermediate (`<domain>`) directories are pure grouping buckets — they MUST NOT contain files. A 1-level path (`root/<topic>`) is allowed when a topic doesn't yet fit any bucket.

```
reports/
├── README.md                              # only file allowed at root
├── .gitignore
├── <domain>/                              # intermediate (pure bucket, files forbidden)
│   └── <topic>/                           # leaf
│       ├── <topic>-2026-07-09.md          # report body
│       ├── <topic>-2026-07-21.md          # older version kept
│       ├── assets/                        # images
│       ├── data/                          # raw data
│       └── scripts/                       # chart-generation code
├── <other-domain>/<topic>/...
└── _template/                             # optional
    └── TEMPLATE.md
```

- **Depth cap**: path segments ≤ 3. `root/a/b` is fine; `root/a/b/c` is forbidden.
- **One topic per leaf** — different topics live in different leaves, so each leaf has one stable URL.
- **Domain freedom**: domain names are author-chosen. Common buckets (`chip-industry/`, `ai-infrastructure/`, `daily/`, ...) will emerge but are not enforced.

## 2. Naming

| Item | Rule |
|---|---|
| Domain dir | English kebab-case, 2–24 chars. Same forbidden chars as topic dir. |
| Topic dir | English kebab-case, 2–24 chars. No spaces, shell-special chars (`#?()<>`), leading/trailing dash, or non-ASCII. |
| Report file | `<descriptive-name>-<YYYY-MM-DD>.md`. Name is free kebab-case (2–40 chars) and **decoupled from path**. No `v2`, `final`, `draft` suffixes. |
| Asset files | `snake_case` (e.g. `chart_valuation.png`). Reusable across versions. |

Same leaf + same filename + same date = conflict → ask. **Historical reports are only added, never overwritten or deleted.** Use `git mv` to preserve history when renaming.

Same filename in different leaves is fine — paths disambiguate. Example: `chip-industry/hbm/market-2026-07-09.md` and `ai-infrastructure/hbm-roadmap/market-2026-07-09.md` are allowed; they are different reports.

## 3. Markdown

- `#` = title; body starts at `##`.
- Images use relative paths: `![alt](assets/chart_xxx.png)`. **No external image URLs.**
- Every image referenced in the body must exist in `assets/`; every file in `assets/` must be referenced somewhere (delete orphans).
- End each report with:
  ```
  ---
  Data as of: YYYY-MM-DD
  Generated: YYYY-MM-DD
  ```
- No base64-embedded images, no raw crawler output (put raw data in `data/`).

## 4. Pre-Write Self-Check

Run through **every item** before any write / move / rename / commit:

- [ ] Correct leaf identified? Path depth ≤ 3?
- [ ] If using an intermediate dir, is it a pure bucket (no files inside)?
- [ ] Filename matches §2 (kebab-case description + ISO date, no version suffix)?
- [ ] Assets placed under the leaf (`assets/`, `data/`, `scripts/`), not root or any intermediate?
- [ ] No new files in root, and no new files in any intermediate directory?
- [ ] Not overwriting an existing file? (Same leaf + same filename + same date = conflict)
- [ ] Not deleting an existing file?
- [ ] Using `git mv` when moving a leaf or renaming a directory, to preserve history?

**If any answer is uncertain, stop and ask the user.**

## 5. After Push — Return URL

After `git commit` + `git push origin main`, return to the user:

- Render: `https://github.com/Xyz9Selu/reports/blob/main/<domain>/<topic>/<file>.md` (or `<topic>/<file>.md` for a 1-level path)
- Tree:   `https://github.com/Xyz9Selu/reports/tree/main/<domain>/<topic>`

`<domain>`, `<topic>`, and `<file>` must match the actual git path **exactly** (case-sensitive on GitHub).

## 6. Forbidden

- **Files in intermediate domain directories** (including `.gitkeep`, `README.md`, shared data) — buckets must contain only topic subdirectories.
- Path depth > 3 (no `root/a/b/c`).
- File names that repeat the parent path components (e.g. `chip-industry-cowos-2026-07-09.md` inside `chip-industry/cowos/`). File names are independent of path.
- Reports, images, or data in the repo root.
- Chinese (or any non-ASCII) characters mixed into paths.
- A lone file standing in as a "topic" — a topic must be a directory.
- External image URLs in place of local `assets/`.
