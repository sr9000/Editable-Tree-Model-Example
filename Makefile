.PHONY: lint dev-setup check-no-reflection

lint:
	autoflake .
	isort . --extend-skip mainwindow.py
	black . --line-length 120 --extend-exclude mainwindow.py

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
