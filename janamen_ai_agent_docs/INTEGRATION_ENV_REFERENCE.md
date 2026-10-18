# Integration environment variables — reference only

**Do not copy this document over the repository's actual `.env.example`.** The current project has its own environment contract in `app/config.py`, `app/gateway/` configuration, Docker Compose, and `.env.example`. The previous generic planning bundle included placeholder names; these are not confirmed names for the existing application.

Before adding/changing variables:

1. Inspect `app/config.py`, gateway config, `docker-compose.yml`, `docs/INTEGRATIONS.md`, and the current `.env.example`.
2. Extend existing settings instead of creating competing settings with similar names.
3. Keep mock/offline behavior as the default.
4. Keep private `.env` files out of version control; use the established protected deployment mechanism.
5. Add validation that blocks live mode when required contracts, credentials, TLS or explicit enable flags are absent.
6. Add config tests for missing settings, invalid combinations and accidental production-mode selection.

## Proposed capability flags (not yet confirmed repository setting names)

The following names are design vocabulary only. Reuse the actual project's names if equivalent settings already exist:

- `ONEC_READ_ENABLED=false`
- `ONEC_WRITE_ENABLED=false`
- `DOCUMENTOLOG_LIVE_SEND_ENABLED=false`
- `AI_EXTERNAL_PROVIDER_APPROVED=false`

A setting name in this list does not mean the capability exists or is connected. Never insert fake credentials or invent 1C endpoints.
