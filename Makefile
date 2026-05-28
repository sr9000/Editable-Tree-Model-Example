.PHONY: lint dev-setup check-no-reflection test gate

lint:
	autoflake .
	isort . \
		--gitignore \
		-s mainwindow.py \
		-s documents/json_tab_ui.py
	black . --line-length 120 --extend-exclude "mainwindow.py|documents/json_tab_ui\.py"

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
test:
	QT_QPA_PLATFORM=offscreen timeout 600 pytest -q $(PYTEST_ARGS)

# Composite DoD gate used after every step of the decouple-jsontab plan.
# Order matches plans/20-decouple-jsontab.md §0.2: lint -> reflection ->
# full test suite. Any failure aborts the chain immediately.
gate: lint check-no-reflection test
