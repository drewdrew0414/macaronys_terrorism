# Contributing

## Folder Ownership

- `macaronys_backend/routers`: FastAPI route handlers.
- `macaronys_backend/services`: business logic and external integrations.
- `macaronys_backend/schemas`: request and response DTOs.
- `macaronys_backend/models.py`: SQLAlchemy models.
- `database/schema.sql`: database schema reference.
- `tests`: regression tests for parser, service, config, and security behavior.

## Commit Messages

Use this format:

```text
type(scope): imperative summary
```

Examples:

```text
feat(discord): add meal and timetable commands
security(worker): require token for worker APIs
docs(readme): document evaluation rubric
test(security): cover missing worker token rejection
```

Keep one logical change per commit when possible. Include verification in the commit body when the change affects security, data flow, or Discord commands.

