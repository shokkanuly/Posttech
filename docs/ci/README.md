# CI template awaiting GitHub workflow permission

`quality.yml` contains the proposed SQLite/PostgreSQL test workflow. It is inactive in this directory. GitHub rejected the active `.github/workflows/quality.yml` push because current authentication lacks `workflow` scope.

After an account owner authorizes GitHub authentication to update workflows, move this file to `.github/workflows/quality.yml` and push. The original active version is also preserved on local branch `codex/fix-plan-ci-local`. No credential was changed or permission expanded by this implementation.

The template also builds an isolated MOCK stack and runs the registration smoke twice with generated private credentials. PostgreSQL verification includes separate application worker processes and a crash after durable gateway acceptance. The local evidence runs backend/lint/typing/locale/syntax, Docker build and smoke commands. This is distinct from a GitHub Actions run. Dependency consistency is checked; continuous vulnerability/secret scanning and activation still need an authorized CI setup. See [the latest integration report](../INTEGRATION_IMPLEMENTATION_REPORT.md).
