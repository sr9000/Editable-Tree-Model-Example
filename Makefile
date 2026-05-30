.PHONY: ui lint dev-setup check-no-reflection test gate

UI_PY := \
	ui/mainwindow.py \
	ui/json_tab_ui.py \
	ui/dialogs/attach_schema_dialog.py \
	ui/dialogs/qmultiline_dialog.py \
	ui/dialogs/qhex_dialog.py \
	ui/dialogs/secret_prefixes_dialog.py

UI_ISORT_SKIP := \
	-s ui/mainwindow.py \
	-s ui/json_tab_ui.py \
	-s ui/dialogs/attach_schema_dialog.py \
	-s ui/dialogs/qmultiline_dialog.py \
	-s ui/dialogs/qhex_dialog.py \
	-s ui/dialogs/secret_prefixes_dialog.py

UI_BLACK_EXCLUDE := "ui/mainwindow.py|ui/json_tab_ui\.py|ui/dialogs/(attach_schema_dialog|qmultiline_dialog|qhex_dialog|secret_prefixes_dialog)\.py"

ui: $(UI_PY)

ui/mainwindow.py: ui/mainwindow.ui
	pyside6-uic $< -o $@

ui/json_tab_ui.py: ui/json_tab.ui
	pyside6-uic $< -o $@

ui/dialogs/attach_schema_dialog.py: ui/dialogs/attach_schema_dialog.ui
	pyside6-uic $< -o $@

ui/dialogs/qmultiline_dialog.py: ui/dialogs/qmultiline_dialog.ui
	pyside6-uic $< -o $@

ui/dialogs/qhex_dialog.py: ui/dialogs/qhex_dialog.ui
	pyside6-uic $< -o $@

ui/dialogs/secret_prefixes_dialog.py: ui/dialogs/secret_prefixes_dialog.ui
	pyside6-uic $< -o $@

lint: ui
	autoflake .
	isort . \
		--gitignore \
		$(UI_ISORT_SKIP)
	black . --line-length 120 --extend-exclude $(UI_BLACK_EXCLUDE)

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

# Full test suite under the offscreen Qt platform with a hard 10-minute
# wall-clock cap (see plans/20-decouple-jsontab.md Step A3 / DoD rules).
# `PYTEST_ARGS` lets callers tack on `-k pattern` or `--lf` without
# editing the recipe.
test: ui
	QT_QPA_PLATFORM=offscreen timeout 600 pytest -q $(PYTEST_ARGS)

# Composite DoD gate used after every step of the decouple-jsontab plan.
# Order matches plans/20-decouple-jsontab.md §0.2: lint -> reflection ->
# full test suite. Any failure aborts the chain immediately.
gate: lint check-no-reflection test
