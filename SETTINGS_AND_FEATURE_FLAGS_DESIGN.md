# Settings and Feature Flag Management Design (Desktop App)

## Goals
- Provide centralized, auditable management of runtime settings and feature flags.
- Allow safe, progressive rollout of future features with fast rollback.
- Keep desktop clients responsive and resilient when offline.
- Enforce least-privilege admin controls for all mutating operations.

## Domain Model

### 1) Setting
A durable runtime configuration value.

- `namespace` (e.g., `ui`, `sync`, `auth`)
- `key` (e.g., `autosave_interval_seconds`)
- `value` (JSON)
- `value_type` (`string`, `int`, `bool`, `json`, `duration`, `enum`)
- `scope` (`global`, `tenant`, `role`, `user`, `device`)
- `status` (`active`, `deprecated`, `locked`)
- `version` (optimistic concurrency)
- `updated_by`, `updated_at`

### 2) Feature Flag
A typed gate controlling code paths.

- `flag_key` (e.g., `new_export_pipeline`)
- `description`
- `flag_type` (`release`, `experiment`, `ops`, `permission`)
- `default_variant` (`off`, `on`, or named variant)
- `variants` (JSON list for multivariate experiments)
- `targeting_rules` (JSON rule DSL)
- `rollout_state` (`draft`, `internal`, `beta`, `ga`, `retired`)
- `owner_team`, `sunset_date`
- `kill_switch` (boolean)
- `updated_by`, `updated_at`, `version`

### 3) Policy / Permission
Defines who can read/update settings and flags.

- Role-based permissions plus optional attribute constraints.
- All writes require explicit capability checks.

## Database Schema Usage

Use relational tables (PostgreSQL/SQLite-compatible for local dev), with immutable history tables for auditability.

### Core tables

1. `app_setting_definition`
   - Metadata and constraints for settings.
   - Columns: `id`, `namespace`, `key`, `value_type`, `default_value_json`, `validation_schema_json`, `is_sensitive`, `created_at`, `updated_at`
   - Unique: `(namespace, key)`

2. `app_setting_value`
   - Current resolved values by scope.
   - Columns: `id`, `definition_id`, `scope_type`, `scope_id`, `value_json`, `version`, `updated_by`, `updated_at`
   - Unique: `(definition_id, scope_type, scope_id)`

3. `feature_flag`
   - Flag metadata and defaults.
   - Columns: `id`, `flag_key`, `flag_type`, `description`, `default_variant`, `variants_json`, `rollout_state`, `kill_switch`, `owner_team`, `sunset_date`, `version`, `updated_by`, `updated_at`
   - Unique: `flag_key`

4. `feature_flag_rule`
   - Ordered targeting rules.
   - Columns: `id`, `flag_id`, `priority`, `rule_json`, `enabled`, `created_at`, `updated_at`
   - Index: `(flag_id, priority)`

5. `feature_flag_override`
   - Explicit per-scope overrides.
   - Columns: `id`, `flag_id`, `scope_type`, `scope_id`, `variant`, `expires_at`, `created_by`, `created_at`
   - Unique: `(flag_id, scope_type, scope_id)`

6. `config_change_event`
   - Outbox/event log for cache invalidation and sync.
   - Columns: `id`, `entity_type`, `entity_id`, `change_type`, `version`, `payload_json`, `created_at`, `published_at`

### History/audit tables

7. `app_setting_value_history`
8. `feature_flag_history`
9. `feature_flag_rule_history`

Each stores pre/post snapshots, actor, reason, correlation ID, and timestamp. Write via DB trigger or application service transactionally.

## Resolution and Precedence

### Settings precedence
`device > user > role > tenant > global > definition default`

### Flag resolution precedence
`kill_switch forced off > explicit override > matching targeting rule > default_variant`

Ensure deterministic rule evaluation:
- Highest priority first.
- First match wins.
- Include stable hashing for percentage rollouts (`hash(user_or_device_id + flag_key) % 100`).

## Admin Permissions Model

Adopt explicit capabilities:

- `settings.read`
- `settings.write`
- `settings.write_sensitive`
- `flags.read`
- `flags.write`
- `flags.rollout`
- `flags.kill_switch`
- `flags.override`
- `audit.read`

### Guarded operations
- Creating/changing definitions: requires `settings.write` and optional dual approval for sensitive settings.
- Editing sensitive values (`is_sensitive=true`): requires `settings.write_sensitive`.
- Rollout state transitions to broader audiences: requires `flags.rollout`.
- Activating kill switch: requires `flags.kill_switch`; must be available in break-glass role.
- Per-user override in production: requires `flags.override` and mandatory expiry.

### Administrative UX controls
- Mandatory change reason for every mutation.
- Optional ticket/reference field (`JIRA-1234`).
- Diff preview before submit.
- Two-person approval workflow for critical flags/settings.

## Caching Approach

Use a layered cache strategy for low-latency desktop reads and safe staleness handling.

### Layers
1. **In-process memory cache**
   - Keyed by `(namespace,key,scope tuple)` and `flag_key + context fingerprint`.
   - Very short TTL (e.g., 15–60s) and version tag.

2. **Local persistent cache (SQLite table or local file)**
   - Last known good snapshot for offline startup.
   - Includes schema version, fetched_at, and signature/checksum.

3. **Server-side cache (optional)**
   - Redis/materialized views for heavy targeting workloads.

### Invalidation
- Publish `config_change_event` on each write.
- Desktop client subscribes via WebSocket/SSE/poll fallback.
- On change event, evict affected keys and re-fetch lazy-on-next-read.
- Force refresh on app resume or network reconnect.

### Consistency strategy
- Eventual consistency is acceptable for non-critical flags.
- For safety-critical flags, enforce synchronous read-through and shorter TTL.
- Never fail-open on policy/permission flags: if unknown, evaluate to safest default (`off`).

## Guardrails for Safe Rollout of Future Features

1. **Flag lifecycle policy**
   - States: `draft -> internal -> beta -> ga -> retired`.
   - Require owner and sunset date at creation.
   - Block merge if code references a retired or expired flag.

2. **Default-safe behavior**
   - All new features behind flag default `off` in production.
   - Unknown flag in client resolves to `off` unless explicitly marked `fail_open` (rare).

3. **Progressive rollout controls**
   - Percentage rollout increments (e.g., 1%, 5%, 25%, 50%, 100%).
   - Segment-based rollout (internal users, tenant allowlist, region).
   - Automated pause/rollback when SLO regression detected.

4. **Observability requirements**
   - Emit exposure events (`flag_key`, variant, actor/context hash, app version).
   - Correlate errors/latency with flag variants in dashboards.
   - Alert on elevated error rate after rollout step.

5. **Operational safety**
   - Global kill switch for each risky subsystem.
   - Time-bound overrides with auto-expiration.
   - Bulk rollback action (revert to prior config snapshot).

6. **Testing and verification gates**
   - Contract tests for setting validation schema.
   - Unit tests for precedence and targeting evaluator.
   - Integration tests for permission checks and audit writes.
   - Canary validation checklist before increasing rollout.

7. **Governance hygiene**
   - Weekly job reports stale flags beyond sunset date.
   - CI lint rule: every flag must include owner + cleanup issue.
   - Quarterly cleanup campaign for dead flags.

## API and Service Shape (suggested)

- `GET /config/settings/resolve?context=...`
- `PATCH /config/settings/{namespace}/{key}`
- `GET /config/flags/evaluate?flag_key=...&context=...`
- `PATCH /config/flags/{flag_key}`
- `POST /config/flags/{flag_key}/rollout-step`
- `POST /config/flags/{flag_key}/kill-switch`
- `GET /config/audit?entity=...`

All mutation endpoints:
- Require idempotency key.
- Require `reason` field.
- Emit audit record + `config_change_event` transactionally.

## Migration and Adoption Plan

1. Introduce schema and read-only admin view.
2. Move existing static settings into `app_setting_definition` + global values.
3. Wrap one non-critical feature with new flag evaluator.
4. Add exposure metrics and rollback automation.
5. Enforce policy gates for all new feature launches.

## Recommended Defaults

- Cache TTL: 30s in-memory, 10m persisted snapshot refresh.
- Max targeting rule count per flag: 50.
- Override expiry required in production (max 14 days).
- Sensitive setting changes require two-person approval.
- Flag sunset date required and <= 180 days by default.
