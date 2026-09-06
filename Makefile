.PHONY: ui lint dev-setup check-no-reflection check-editors-isolation check-tree-isolation test gate requirements

UI_PY := \
	ui/mainwindow.py \
	ui/json_tab_ui.py \
	ui/dialogs/attach_schema_dialog.py \
	ui/dialogs/qmultiline_dialog.py \
	ui/dialogs/qhex_dialog.py \
	ui/dialogs/secret_prefixes_dialog.py

ui: $(UI_PY)

ui/mainwindow.py: ui/mainwindow.ui
	poetry run pyside6-uic $< -o $@

ui/json_tab_ui.py: ui/json_tab.ui
	poetry run pyside6-uic $< -o $@

ui/dialogs/attach_schema_dialog.py: ui/dialogs/attach_schema_dialog.ui
	poetry run pyside6-uic $< -o $@

ui/dialogs/qmultiline_dialog.py: ui/dialogs/qmultiline_dialog.ui
	poetry run pyside6-uic $< -o $@

ui/dialogs/qhex_dialog.py: ui/dialogs/qhex_dialog.ui
	poetry run pyside6-uic $< -o $@

ui/dialogs/secret_prefixes_dialog.py: ui/dialogs/secret_prefixes_dialog.ui
	poetry run pyside6-uic $< -o $@

lint: ui
	poetry run autoflake .
	poetry run isort .
	poetry run black .

# Activate the repo-local git hooks for every fresh clone.
# Idempotent — safe to run multiple times.
dev-setup:
	git config core.hooksPath .githooks
	@chmod +x .githooks/pre-commit .githooks/pre-commit-ci
	@echo "git hooks active at .githooks/ (see plans/10-allowlist-and-precommit-hook.md)"

# Whole-tree scan: fails the build on any new getattr/hasattr outside
# the allowlist. Mirrors the staged-files check in .githooks/pre-commit.
check-no-reflection:
	bash .githooks/pre-commit-ci

# Responsibility-segregation §2.5: editors/ must not import app/documents/tree
# (concrete widgets) or app/documents (the dispatch seam). Standalone target so
# it can be run in isolation; also runs inside `check-no-reflection` via the hook.
check-editors-isolation:
	bash .githooks/_check_editors_isolation.sh

# Tree isolation: tree/ must not import app/documents/editors/delegates/state/validation.
# Standalone target so it can be run in isolation; also runs inside
# `check-no-reflection` via the hook.
check-tree-isolation:
	bash .githooks/_check_tree_isolation.sh

# Full test suite under the offscreen Qt platform with a hard 10-minute
# wall-clock cap (see plans/20-decouple-jsontab.md Step A3 / DoD rules).
# `PYTEST_ARGS` lets callers tack on `-k pattern` or `--lf` without
# editing the recipe.
test: ui
	QT_QPA_PLATFORM=offscreen timeout 600 poetry run pytest -q $(PYTEST_ARGS)

# Composite DoD gate used after every step of the decouple-jsontab plan.
# Order matches plans/20-decouple-jsontab.md §0.2: lint -> reflection ->
# full test suite. Any failure aborts the chain immediately.
gate: lint check-no-reflection test

# requirements.txt is GENERATED from poetry.lock — never edit it by hand.
# Regenerate after any dependency change and commit the result.
requirements:
	poetry export --only main --without-hashes -f requirements.txt -o requirements.txt
