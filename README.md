# Desktop App Scaffold (PySide6 + SQLAlchemy + Liquibase)

This scaffold provides:

- A typed, environment-first config model (`pydantic-settings`).
- A composition root for dependency injection.
- Structured logging setup.
- SQLAlchemy engine/session factories.
- A dedicated Liquibase runner with a **safe startup checkpoint** before UI launch.
- A simple PySide6 startup flow.

## Startup flow

1. Load settings from env + `.env`.
2. Configure logging.
3. Build dependency container.
4. Run Liquibase update if enabled.
5. Create Qt app + main window.
6. Start event loop.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
python -m app.main
```
