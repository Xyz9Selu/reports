# Reports Repo Convention

Public reports repo. **Every AI agent MUST read and follow this file before creating, moving, renaming, or committing anything.** When in doubt, ask — do not act.

**Repo:** `https://github.com/Xyz9Selu/reports`

---

## 1. Structure

One topic = one directory. The directory holds every version of a report and all its assets. The root contains only `README.md` and `.gitignore`.

```
reports/
├── README.md
├── .gitignore
├── cpo-optical/                    # topic directory (kebab-case)
│   ├── cpo-optical-2026-07-09.md   # report body
│   ├── cpo-optical-2026-07-21.md   # older version is kept
│   ├── assets/                     # images
│   ├── data/                       # raw data
│   └── scripts/                    # chart-generation code
└── _template/TEMPLATE.md           # optional
```

## 2. Naming

| Item | Rule |
|---|---|
| Topic directory | English kebab-case, 2–24 chars. No spaces, shell-special chars (`#?()<>`), leading/trailing dash, or non-ASCII. |
| Report file | `<directory>-<YYYY-MM-DD>.md`. ISO date is the version. No `v2`, `final`, `draft` suffixes. |
| Asset files | `snake_case` (e.g. `chart_valuation.png`). Reusable across versions. |

Same filename + same date = conflict → ask the user. **Historical reports are only added, never overwritten or deleted.** Use `git mv` to preserve history when renaming.

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

- [ ] Correct topic identified? Directory exists (or is being created)?
- [ ] Filename matches §2?
- [ ] Assets placed under the topic directory (`assets/`, `data/`, `scripts/`), not root?
- [ ] No new files in root?
- [ ] Not overwriting an existing file? (Same name + same date = conflict)
- [ ] Not deleting an existing file?
- [ ] Using `git mv` when renaming, to preserve history?

**If any answer is uncertain, stop and ask the user.**

## 5. After Push — Return URL

After `git commit` + `git push origin main`, return to the user:

- Render: `https://github.com/Xyz9Selu/reports/blob/main/<dir>/<file>.md`
- Tree:   `https://github.com/Xyz9Selu/reports/tree/main/<dir>`

`<dir>` and `<file>` must match the actual git path **exactly** (case-sensitive on GitHub).

## 6. Forbidden

- Reports, images, or data in the repo root.
- Multiple topics in one directory, or one topic split across multiple directories.
- Spaces or shell-special characters in any path.
- Chinese (or any non-ASCII) characters mixed into paths.
- A lone file standing in as a "topic" — a topic must be a directory.
- External image URLs in place of local `assets/`.
