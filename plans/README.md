# Plans

Each file describes one feature, broken into per-file commits with a
Definition of Done (DoD) per commit. Read order is independent — features
do not depend on each other — but if shipped together the suggested order is
01 → 02 → 03 (smallest blast radius first).

| # | File | Feature |
|---|---|---|
| 01 | [`01-utc-datetime.md`](01-utc-datetime.md) | UTC datetime with `Z` suffix; smart conversions across the date/time family, including real timezone-shift on `DATETIMEZONE → DATETIMEUTC`. |
| 02 | [`02-number-affix.md`](02-number-affix.md) | ✅ Done — Integers and floats with a textual prefix **or** suffix (never both); stored as structured `NumberAffix`; optional space between affix and number is preserved. |
| 03 | [`03-secret-strings.md`](03-secret-strings.md) | `SECRET` text variant; never auto-classified as another text kind; hidden by default; detected by configurable field-name patterns. |

## Conventions used in every plan

- **One commit per file.** A test file added alongside its production target
  counts as the same commit.
- **DoD is testable.** It either lists concrete unit tests or a documented
  manual smoke check; "looks fine" is not a DoD.
- **No cross-feature changes inside a feature plan.** Shared touchpoints
  (e.g. `tree/types.py`) are scheduled as their own commit per feature, not
  bundled.
- **Docs commit is last** for each plan and contains no code changes.
