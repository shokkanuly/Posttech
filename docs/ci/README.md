# CI template awaiting GitHub workflow permission

`quality.yml` contains the proposed SQLite/PostgreSQL test workflow. It is inactive in this directory. GitHub rejected the active `.github/workflows/quality.yml` push because current authentication lacks `workflow` scope.

After an account owner authorizes GitHub authentication to update workflows, move this file to `.github/workflows/quality.yml` and push. The original active version is also preserved on local branch `codex/fix-plan-ci-local`. No credential was changed or permission expanded by this implementation.

The local evidence runs the same backend/lint/typing/locale/syntax commands. This is distinct from a GitHub Actions run. See [implementation report](../FIX_PLAN_IMPLEMENTATION_REPORT.md).
