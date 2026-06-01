# Refactor Plan — Resolve `tree/` Upward Imports

**Status:** Proposed
**Created:** 2026-06-01
**Source:** `reports/code-quality-audit-2026-06-01.md` §1.2, §2, §8
(High Priority #1)
**Owner branch suggestion:** `fix-tree-upward-imports`

---

## 1. Problem statement

`tree/` is documented as the low-level data package — nothing should sit
below it. The audit found **11 upward imports** that invert this rule
(verified 2026-06-01):

| From                    | Import                                              | Kind  |
|:------------------------|:----------------------------------------------------|:------|
| `tree/types.py:12`      | `editors.inline.datetime.parse_datetime_text`       | eager |
| `tree/item.py:6`        | `editors.inline.datetime.enums.DateTimeCategory`    | eager |
| `tree/item.py:7`        | `editors.inline.datetime.regex.parse_datetime_text` | eager |
| `tree/item.py:8`        | `state.secret_settings.get_secret_word_prefixes`    | eager |
| `tree/item.py:13`       | `validation.secret_names.name_looks_secret`         | eager |
| `tree/item_coercion.py:11` | `editors.inline.datetime.enums.DateTimeCategory` | eager |
| `tree/item_coercion.py:12` | `editors.inline.datetime.regex.parse_datetime_text` | eager |
| `tree/item_coercion.py:276,368,475,504` | `delegates.formatting.bytes_codec` | lazy  |
| `tree/item_coercion.py:539` | `delegates.formatting.color_codec`             | lazy  |

Lazy imports avoid circular-import crashes, but the dependency direction
is wrong and blocks the codebase from an architectural **A**.

These imports fall into **three independent concerns**, each tackled by
its own step so they can land and be reviewed separately.

---

## 2. Guiding principle

The shared code being imported is **pure data-layer logic** (parsing,
encoding) — it only lives in `editors/` / `delegates/` for historical
reasons. The fix is to **move it down**, not to add indirection. State /
validation coupling is removed by **dependency injection**.

After this plan:

```
tree/  →  core/ (or tree-internal)   # datetime parsing + codecs
tree/  →  (nothing above it)
editors/, delegates/  →  core/       # consume the shared code downward
```

CI gate to add: extend the existing import-direction checks (alongside
`make check-editors-isolation`) with a `make check-tree-isolation` that
forbids `tree/` importing `app/`, `documents/`, `editors/`,
`delegates/`, `state/`, `validation/`.

---

## 3. Steps

### Step 1 — Extract shared datetime parsing (resolves 5 imports)

`editors/inline/datetime/regex.py` and `enums.py` contain **no Qt code**
— they are pure parsing logic. Move the pure parts to a shared location.

1. Create `core/datetime_parsing/` (new top-level package) with:
   - `enums.py` ← `DateTimeCategory` (moved verbatim).
   - `regex.py` ← `parse_datetime_text` + its regex tables (moved
     verbatim).
2. Re-export from `editors/inline/datetime/__init__.py` so existing
   editor imports keep working:
   `from core.datetime_parsing.regex import parse_datetime_text`.
3. Repoint the data layer:
   - `tree/types.py`, `tree/item.py`, `tree/item_coercion.py` import
     from `core.datetime_parsing` instead of `editors.inline.datetime`.
4. Run the datetime + coercion suites.

**Affected:** `tree/types.py`, `tree/item.py`, `tree/item_coercion.py`,
`editors/inline/datetime/{__init__,regex,enums}.py`, new `core/`.

### Step 2 — Move bytes/color codecs down (resolves 6 imports)

`delegates/formatting/bytes_codec.py` and `color_codec.py` are
encode/decode helpers — a **storage concern**, not presentation.

1. Move `bytes_codec.py` and `color_codec.py` to `tree/codecs/`
   (or `core/codecs/` if you prefer them framework-neutral). They have
   no Qt dependency, so either works; `tree/codecs/` keeps them adjacent
   to their only data-layer caller.
2. Replace the 5 lazy `from delegates.formatting.bytes_codec import …`
   and the 1 `color_codec` import in `tree/item_coercion.py` with eager
   top-level imports from the new location (lazy was only needed to dodge
   the circular dependency, which now disappears).
3. Repoint `delegates/formatting/value_formatting.py` and any other
   `delegates/` / `editors/` consumers to the new location (keep a thin
   re-export shim in `delegates/formatting/__init__.py` for one release
   if external callers exist).
4. Run bytes/zlib/gzip + color + coercion suites.

**Affected:** `tree/item_coercion.py`, `delegates/formatting/*`, new
`tree/codecs/` (or `core/codecs/`).

### Step 3 — Inject secret-name matching (resolves 2 imports)

`tree/item.py` reaches into `state.secret_settings` and
`validation.secret_names`. Invert via constructor injection.

1. Define a tiny callable seam consumed by `JsonTreeItem`:
   `SecretNamePredicate = Callable[[str], bool]`.
2. Add an optional parameter to `JsonTreeItem.__init__`
   (e.g. `secret_name_predicate: SecretNamePredicate | None = None`),
   defaulting to a module-level adapter that calls the current
   `name_looks_secret(name, get_secret_word_prefixes())`.
3. Wire the real predicate from the composition layer
   (`documents/composition/`) where `state/` and `validation/` are
   already legitimate dependencies, so production behaviour is
   unchanged.
4. The default keeps headless `JsonTreeItem(...)` test fixtures working
   without extra wiring; only the *import location* moves out of the hot
   data path.

> Note: a full inversion would also remove the default import. Keep the
> default for now (lowest risk); the import becomes a composition-time
> detail rather than a `tree/` hard dependency. If a stricter gate is
> desired, move `name_looks_secret` (22 lines, pure) into `core/` and
> have both `validation/` and `tree/` import it downward.

**Affected:** `tree/item.py`, `documents/composition/*`, optionally a
new `core/secret_names.py`.

### Step 4 — Add the import-direction gate

1. Add `scripts/check_tree_isolation.py` (mirror
   `check-editors-isolation`): fail if any `tree/*.py` imports `app`,
   `documents`, `editors`, `delegates`, `state`, or `validation`.
2. Wire `make check-tree-isolation` into `make gate`.
3. Update `ai-memory/repo-map.md` §3 invariants to document the new rule
   and the `core/` package.

---

## 4. Sequencing & risk

- Steps 1–3 are **independent** and can land in any order / separate PRs.
- Step 4 should land **last** (it will fail until 1–3 are done) — or land
  first as an *allow-list* that shrinks per step.
- **Risk: Low.** All moved code is pure (no Qt, no state). The only
  behavioural surface is the re-export shims; covered by existing
  datetime, coercion, bytes, and color suites.
- **No runtime behaviour change** is intended. The plan is purely
  structural.

## 5. Definition of done

- [ ] `grep -rn "from editors\|from delegates\|from state\|from validation" tree/`
      returns nothing.
- [ ] `make check-tree-isolation` passes and is part of `make gate`.
- [ ] All previously passing suites still pass (1124 collected).
- [ ] `repo-map.md` documents `core/` and the tree-isolation rule.
- [ ] Audit table in §2 of the report is fully resolved (0 upward
      imports).

---

## 6. Out of scope (tracked separately in `todo-n-fixme.md`)

These appear in the same audit but are **not** part of this plan:

- Splitting `tree_actions/structure.py` (774 lines).
- Extracting a `FileOperationsPresenter` from `MainWindow`.
- Narrowing `IoController.save()` exception handling.
- Delegate-matrix / I/O round-trip / model-invariant test gaps.
- Pinning `pytest-qt`, coverage snapshot, `Document`-conformance check.
</content>
