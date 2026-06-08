# Security Policy

## Secret Handling

- Keep runtime secrets only in `.env` or the deployment secret manager.
- Commit `.env.example` only with placeholder values.
- Rotate immediately if a Discord bot token, database URL, worker token, webhook URL, or NEIS API key is exposed.

## Required Controls

- Worker endpoints require `X-Worker-Token`.
- Discord destructive commands require a staff channel and confirmation words.
- Discord bot invite permissions use the least-privilege integer in `config.json`; do not use full admin permission unless debugging in a private test server.
- Moderation actions are written to audit tables.
- External API calls use bounded timeouts.

## Severity Rubric

- Grade 4: exposed credentials, unauthenticated worker/admin API, destructive command bypass.
- Grade 3: over-privileged bot permissions, missing audit trail, broad data exposure.
- Grade 2: weak validation, missing timeout, unsafe default.
- Grade 1: minor hardening or documentation gap.
