# Liquibase Migration Plan

> Assumption: the concrete schema DDL was referenced outside this repository context. This plan is structured so each object from the existing schema can be mapped into deterministic Liquibase changesets.

## 1) Master changelog organization

Use one immutable master changelog per application line, with include ordering that mirrors dependency direction.

```xml
<!-- db/changelog/db.changelog-master.xml -->
<databaseChangeLog
    xmlns="http://www.liquibase.org/xml/ns/dbchangelog"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.liquibase.org/xml/ns/dbchangelog
                        http://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-latest.xsd">

    <include file="db/changelog/releases/R2026.04.0.xml" relativeToChangelogFile="false"/>
</databaseChangeLog>
```

Release file pattern:

```xml
<!-- db/changelog/releases/R2026.04.0.xml -->
<databaseChangeLog>
  <include file="db/changelog/common/001-baseline-schemas.xml"/>
  <include file="db/changelog/common/010-tables-core.xml"/>
  <include file="db/changelog/common/020-constraints-pk-uk.xml"/>
  <include file="db/changelog/common/030-fk.xml"/>
  <include file="db/changelog/common/040-indexes.xml"/>
  <include file="db/changelog/common/050-views.xml"/>
  <include file="db/changelog/common/060-routines.xml"/>
  <include file="db/changelog/common/900-reference-data.xml"/>
  <include file="db/changelog/env/910-env-dev-test-only.xml"/>
</databaseChangeLog>
```

Guidelines:
- Keep files append-only.
- Never modify executed changesets in shared environments.
- New changes go in a new release file (e.g., `R2026.04.1.xml`) and are then included by master.

## 2) Changeset design

Naming standard:
- `id`: `YYYYMMDD-HHMM-<seq>-<short-action>`
- `author`: team alias (e.g., `db-platform`)

Examples:
- `20260408-0900-001-create-user-table`
- `20260408-0905-002-add-user-email-uk`

Design rules:
1. One logical change per changeset.
2. Separate table creation from index/constraint creation where rollout risk differs.
3. Always include rollback blocks.
4. Use `runInTransaction="true"` unless vendor limitations require otherwise.
5. Use `logicalFilePath` when files are moved to preserve checksum lineage.

## 3) Labels and contexts

### Labels (feature/release semantics)
Use labels for business capability and release grouping:
- `release:R2026.04.0`
- `feature:billing`
- `feature:identity`
- `hotfix`
- `seed:reference`

### Contexts (environment execution scope)
Use contexts for environment behavior:
- `common` (all envs)
- `dev`
- `test`
- `prod`
- `nonprod` (dev+test)
- `backfill` (controlled data migration runs)

Policy:
- Structural DDL for all environments: `context="common"`
- Non-production seed/test helpers: `context="nonprod"`
- Production-only operational DDL (rare): `context="prod"`

Execution examples:
- Dev: `--contexts=common,dev,nonprod --labels="release:R2026.04.0"`
- Test: `--contexts=common,test,nonprod --labels="release:R2026.04.0"`
- Prod: `--contexts=common,prod --labels="release:R2026.04.0"`

## 4) Preconditions strategy

Use fail-fast preconditions for destructive/risky operations, and idempotency guards for additive operations.

Patterns:
1. Guard create-if-not-exists:
   - `not tableExists`
   - `onFail="MARK_RAN"` for safe no-op
2. Guard alter/drop:
   - `columnExists` / `indexExists`
   - `onFail="HALT"` when state drift indicates risk
3. Data prechecks before constraint hardening:
   - `sqlCheck expectedResult="0"` for duplicates/nulls before adding `NOT NULL`/`UNIQUE`
4. Vendor gating:
   - `dbms type="postgresql"` etc.

Example:
```xml
<changeSet id="20260408-1000-010-add-order-number-uk" author="db-platform" context="common" labels="release:R2026.04.0,feature:orders">
  <preConditions onFail="HALT" onError="HALT">
    <tableExists tableName="orders"/>
    <columnExists tableName="orders" columnName="order_number"/>
    <sqlCheck expectedResult="0">
      SELECT COUNT(*) FROM (
        SELECT order_number FROM orders GROUP BY order_number HAVING COUNT(*) > 1
      ) d
    </sqlCheck>
  </preConditions>
  <addUniqueConstraint tableName="orders" columnNames="order_number" constraintName="uk_orders_order_number"/>
  <rollback>
    <dropUniqueConstraint tableName="orders" constraintName="uk_orders_order_number"/>
  </rollback>
</changeSet>
```

## 5) Reference data seed strategy

Split reference/static data from transactional data migrations.

Structure:
- `900-reference-data.xml` for mandatory static data (country codes, statuses, enum-like lookup values)
- `905-reference-data-nonprod.xml` for sample/demo data with `context="nonprod"`

Practices:
1. Use deterministic keys (natural code or fixed UUID).
2. Use `loadUpdateData` (upsert semantics) where available; otherwise SQL MERGE/UPSERT per DB.
3. Add checksum-compatible updates as new changesets, not by editing old seed files.
4. For deletes/deprecations, use soft-delete flags where possible.

## 6) Rollback approach

Use a two-layer rollback policy:

1. **Immediate technical rollback (Liquibase rollback):**
   - Every changeset includes explicit rollback.
   - Favor reversible operations in one deployment unit.
   - Avoid irreversible `dropColumn` in same release as app cutover.

2. **Forward-fix rollback (preferred for prod after data mutation):**
   - For destructive/data-transforming changes, treat rollback as forward patch.
   - Maintain backup tables or shadow columns during transition window.

Release-level rollback checkpoints:
- Tag before deploy: `pre-R2026.04.0`
- Tag after successful deploy: `post-R2026.04.0`
- If needed: `liquibase rollback --tag=pre-R2026.04.0`

## 7) Release tagging and promotion (dev/test/prod)

Promotion should reuse the exact same changelog artifacts.

Workflow:
1. Build release branch and freeze changelog for `R2026.04.0`.
2. Tag DB state in each env before applying:
   - `dev-pre-R2026.04.0`, `test-pre-R2026.04.0`, `prod-pre-R2026.04.0`
3. Apply with env contexts.
4. Validate (schema drift check + smoke SQL + app checks).
5. Tag post state:
   - `dev-post-R2026.04.0`, etc.

Recommended commands:
- `liquibase validate`
- `liquibase status --verbose`
- `liquibase updateSQL` (review before `update`)
- `liquibase update`
- `liquibase tag <env-pre-release-tag>` before deployment

Promotion controls:
- Dev allows `nonprod` seeds and experimental labels.
- Test mirrors prod contexts plus nonprod-only data if required for QA.
- Prod runs only `common,prod` and approved labels.

## 8) Suggested folder structure

```text
db/
  changelog/
    db.changelog-master.xml
    releases/
      R2026.04.0.xml
      R2026.04.1.xml
    common/
      001-baseline-schemas.xml
      010-tables-core.xml
      020-constraints-pk-uk.xml
      030-fk.xml
      040-indexes.xml
      050-views.xml
      060-routines.xml
      900-reference-data.xml
    env/
      905-reference-data-nonprod.xml
      910-env-dev-test-only.xml
```

## 9) Mapping checklist for “schema above”

When translating your existing schema into Liquibase:
1. List objects in dependency order (schema → tables → PK/UK → FK → indexes → views/routines).
2. Convert each object to one or more changesets using naming/label/context conventions above.
3. Add preconditions for each non-create operation.
4. Place static lookup data into `900-reference-data.xml`.
5. Define rollback for every changeset; flag forward-fix-only cases.
6. Dry-run with `updateSQL`, then apply in dev with tags.
7. Promote unchanged artifacts to test, then prod.
