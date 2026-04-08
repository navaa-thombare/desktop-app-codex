# PySide6 Desktop Application Architecture (Modular Monolith)

## 1) Goals and Architectural Style

This design targets a long-lived desktop product with:

- **Rich desktop UX** via PySide6.
- **Strong data integrity** via PostgreSQL.
- **Versioned schema evolution** via Liquibase.
- **High maintainability and extensibility** via a **modular monolith**.

A modular monolith keeps deployment and operational overhead low (single app artifact) while preserving clean boundaries so modules can later become services if needed.

---

## 2) Module Boundaries

Use business capabilities as first-class modules. Every module owns its domain model, application services, repository interfaces, and adapters.

### Core modules (example)

1. **identity_access**
   - Users, roles, permissions, authentication session metadata.
   - Exposes authorization checks to other modules.

2. **customer_management**
   - Customer profiles, contacts, segmentation fields.

3. **catalog**
   - Product/service definitions, pricing metadata, versioning.

4. **sales_orders**
   - Quotes, orders, line items, status transitions.
   - Depends on `customer_management` and `catalog` through published application interfaces only.

5. **billing**
   - Invoices, payment states, reconciliation records.
   - Depends on `sales_orders` published events and interfaces.

6. **reporting**
   - Read-model-centric aggregations and exports.
   - Consumes events and query interfaces; must not mutate domain state of other modules.

7. **desktop_shell**
   - PySide6 composition root, navigation, dependency wiring, view hosting.
   - No domain logic.

8. **platform**
   - Shared technical capabilities: config loading, logging, event bus, DB unit-of-work, migration orchestration, security utilities.

### Boundary principles

- **Inward dependencies only** (UI/adapters -> application -> domain).
- Module internals are private; expose only explicit APIs (`application/public.py` or similar).
- Cross-module communication defaults to:
  - synchronous application service calls for transactional needs,
  - domain/integration events for decoupled workflows.

---

## 3) Recommended Repository Layout

```text
repo/
  pyproject.toml
  README.md
  .env.example
  liquibase/
    changelog/
      db.changelog-master.xml
      modules/
        identity_access/
        customer_management/
        catalog/
        sales_orders/
        billing/
        reporting/
  src/
    app/
      bootstrap/
        container.py
        startup.py
      desktop_shell/
        ui/
          main_window.py
          widgets/
        presenters/
        viewmodels/
      platform/
        config/
          settings.py
        db/
          sqlalchemy/
            models/
            repositories/
          unit_of_work.py
          transaction.py
        logging/
          setup.py
          context.py
        events/
          bus.py
        security/
      modules/
        identity_access/
          domain/
          application/
          infrastructure/
          api.py
        customer_management/
          domain/
          application/
          infrastructure/
          api.py
        catalog/
          domain/
          application/
          infrastructure/
          api.py
        sales_orders/
          domain/
          application/
          infrastructure/
          api.py
        billing/
          domain/
          application/
          infrastructure/
          api.py
        reporting/
          domain/
          application/
          infrastructure/
          api.py
  tests/
    unit/
    integration/
    contract/
  scripts/
    dev/
    release/
```

### Internal layering per module

- `domain/`: entities, value objects, domain services, domain events (no framework imports).
- `application/`: use-cases, commands/queries, DTOs, ports.
- `infrastructure/`: PostgreSQL repositories, external integrations.
- `api.py`: stable module facade used by other modules and UI shell.

---

## 4) Dependency Rules (Critical)

Enforce these rules with import-linting (e.g., `import-linter`) and CI:

1. `desktop_shell` may depend on `modules/*/api.py` and `platform/*`; never on module internals.
2. `module_X.domain` depends on nothing outside itself (except shared pure domain primitives).
3. `module_X.application` can depend on `module_X.domain` and declared ports.
4. `module_X.infrastructure` can depend on `module_X.application` and `platform` adapters.
5. Cross-module imports only via `<module>.api` or published contracts/events.
6. No cyclic dependencies among modules.
7. `platform` cannot depend on business modules.

Use explicit anti-corruption adapters for legacy or external systems.

---

## 5) PostgreSQL + Liquibase Strategy

### PostgreSQL

- One PostgreSQL database; modular ownership by schema namespace or strict table prefixes.
- Each module owns its tables and migration files.
- Use SQLAlchemy 2.x for ORM/data mapping where useful; allow hand-written SQL for reporting read paths.

### Liquibase

- Single master changelog includes per-module changelogs.
- Naming convention for changesets:
  - `<module>-<YYYYMMDD>-<short-description>`
- Every changeset includes rollback logic where feasible.
- Migration pipeline:
  1. Dev startup optionally runs `liquibase update`.
  2. CI validates changelogs (`liquibase validate`) and dry-runs SQL generation.
  3. Release process runs migrations before app rollout (or first-launch gated migration in controlled environments).

### Transaction boundaries

- Unit-of-work per application use-case.
- Avoid distributed transactions between modules in-process; coordinate with domain events and compensating actions.

---

## 6) Configuration Strategy

Use typed settings (e.g., `pydantic-settings`) with layered sources:

1. **Default settings module** (safe defaults).
2. **Environment file** (`.env`) for local development.
3. **Environment variables** for CI/release overrides.
4. **OS keychain/secret manager** for sensitive runtime secrets (DB password, API keys).

### Config structure

- `AppConfig`: app metadata, environment, feature flags.
- `DbConfig`: host, port, dbname, pool sizing, SSL mode.
- `LoggingConfig`: level, sinks, rotation, structured/JSON toggle.
- `UiConfig`: theme, localization defaults, accessibility toggles.

### Rules

- No raw `os.getenv` outside config package.
- Configuration injected through composition root.
- Feature flags are read-only at runtime unless explicitly supporting hot reload.

---

## 7) Logging and Observability Approach

Adopt structured logging from day one.

### Logging design

- Library: stdlib `logging` with structured formatter (`structlog` or JSON formatter).
- Required fields:
  - `timestamp`, `level`, `module`, `use_case`, `user_id` (if authenticated), `correlation_id`, `session_id`.
- Sinks:
  - rotating local file,
  - stderr for dev,
  - optional remote sink (OTLP/HTTP) for enterprise deployments.

### Correlation and diagnostics

- Generate a correlation ID per user-triggered action in UI.
- Propagate context through application services and repository calls.
- Log domain events publication and handler completion.
- Never log sensitive fields (passwords, access tokens, PCI/PII without masking).

### Error handling

- Global PySide6 exception hook:
  - user-friendly dialog,
  - detailed structured log with traceback,
  - optional crash report packaging.

---

## 8) Desktop Packaging and Distribution

Target multiple distribution modes:

1. **Internal/enterprise installer**
   - Build with PyInstaller or Nuitka.
   - Sign binaries (Windows Authenticode, macOS notarization).

2. **Auto-update capable channel**
   - Versioned release manifests.
   - Delta update support where possible.

3. **Portable/dev mode**
   - Faster iteration build for QA and support.

### Packaging considerations

- Include Qt plugins/resources explicitly (platforms, imageformats, styles).
- Bundle Liquibase executable/JAR strategy (or pre-migration step in installer).
- Validate DB connectivity and migration status during first-run bootstrap.
- Keep app-writable data in OS-appropriate paths:
  - logs, cache, local exports, and user preferences.

### Release hardening checklist

- Reproducible builds.
- SBOM generation.
- Dependency vulnerability scan.
- Signing + notarization verification.
- Smoke test on clean OS VM.

---

## 9) Extensibility Roadmap

Design now for future evolution without microservice overhead today.

- **Module API contracts** become extraction seams if a module is later split out.
- **Event catalog** in code and docs enables decoupled feature growth.
- **Plugin points** in `desktop_shell` (menu contributions, views, commands).
- **Feature flags** support incremental rollout.
- **Contract tests** ensure module API compatibility.

Potential future extraction candidates:
- reporting,
- billing integrations,
- identity federation.

---

## 10) Governance and Quality Gates

- Architecture decision records (ADRs) for major choices.
- Import boundary checks enforced in CI.
- Mandatory tests per module:
  - domain unit tests,
  - application service tests,
  - repository integration tests against ephemeral PostgreSQL.
- Migration policy: no destructive schema changes without deprecation window.

---

## 11) Suggested Starter Stack (Python)

- **UI:** PySide6
- **ORM/DB:** SQLAlchemy 2.x + psycopg (v3)
- **Migrations:** Liquibase (XML/YAML/SQL changelogs)
- **Config:** pydantic-settings
- **DI/container:** `punq` or lightweight manual container
- **Logging:** stdlib logging + structlog JSON processor
- **Testing:** pytest + testcontainers-postgres
- **Boundary enforcement:** import-linter

This combination keeps the architecture explicit, testable, and enterprise-ready while preserving a single deployable desktop artifact.
