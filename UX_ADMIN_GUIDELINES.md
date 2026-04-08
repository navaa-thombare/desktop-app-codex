# Enterprise PySide6 Admin Application UX Guidelines

## 1) Design Intent and Principles

This guide defines UX standards for a professional, enterprise-grade PySide6 admin desktop application.

### Core principles

- **Speed for experts:** Minimize clicks and support keyboard-first workflows.
- **Predictability:** Reuse consistent patterns for navigation, forms, and data grids.
- **Safety:** Prevent destructive mistakes with clear validation and confirmation patterns.
- **Operational clarity:** Always communicate loading, empty, and error states explicitly.
- **Accessibility:** Ensure readable typography, focus visibility, and full keyboard operability.

---

## 2) Screen Inventory

Model the product around reusable screen archetypes.

## 2.1 Global shell screens

1. **Sign-in**
   - Username/password or SSO launch.
   - Environment badge (Dev/Test/Prod).
2. **Main workspace shell**
   - Global navigation, top command bar, content area, status footer.
3. **User profile/preferences**
   - Theme, density, locale, keyboard shortcut reference.
4. **Notifications center**
   - Recent alerts, task outcomes, background job results.
5. **Audit/log viewer**
   - Read-only operational trace for privileged users.

## 2.2 Module workspace screens

Per domain module (e.g., users, customers, catalog, orders, billing), include:

1. **List screen (index)**
   - Data grid + filter panel + quick actions.
2. **Detail screen (read mode)**
   - Structured overview and related records tabs.
3. **Create/Edit screen**
   - Sectioned forms with inline validation.
4. **Bulk operation screen**
   - Batch update, import, export, reassignment.
5. **Approval/review screen** (where needed)
   - Side-by-side diffs, comments, decision actions.

## 2.3 Utility screens

1. **Settings / administration**
   - Role management, integrations, feature flags.
2. **Job monitor**
   - Long-running imports/exports/sync job statuses.
3. **Help and diagnostics**
   - Version/build metadata, support bundle generation.

---

## 3) Navigation Model

Use a **three-level model** to support depth without disorientation.

## 3.1 Level 1: Primary modules

- Left rail (collapsible) with top-level modules.
- Order by business frequency, not alphabet.
- Each item has icon + label.
- Allow pinning up to 5 favorite modules.

## 3.2 Level 2: Workspace views

- Module-local secondary nav (tabs or segmented control).
- Typical entries: List, Saved Views, Queue, Reports.

## 3.3 Level 3: In-screen hierarchy

- Within screen: tabs/accordions for related objects.
- Breadcrumb line for deep paths:
  - `Orders > SO-102938 > Invoice > INV-3932`

## 3.4 Global command surface

- **Command palette** (`Ctrl+K`) for navigation and actions.
- **Global search** for records and screens.
- **Recent items** (`Alt+Left/Right` navigation history).

## 3.5 Window and tab behavior

- Prefer **single-window app** with optional detachable utility windows.
- Permit multi-tab record editing within module context.
- Warn on unsaved changes before closing tab/window.

---

## 4) Keyboard Shortcuts

Shortcuts must be discoverable via Help > Keyboard Shortcuts and command palette hints.

## 4.1 Global shortcuts

- `Ctrl+K` — Open command palette
- `Ctrl+F` — Focus search/filter in current context
- `Ctrl+N` — Create new record (if permitted)
- `Ctrl+S` — Save current form
- `Ctrl+R` — Refresh current view
- `Ctrl+W` — Close current tab
- `Ctrl+Tab` / `Ctrl+Shift+Tab` — Next/previous tab
- `F1` — Context help
- `Esc` — Close dialog/cancel transient mode

## 4.2 Grid shortcuts

- `↑/↓` — Move row selection
- `Shift+↑/↓` — Extend row selection
- `Enter` — Open selected row detail
- `Space` — Toggle row checkbox
- `Ctrl+A` — Select all visible rows
- `Ctrl+C` — Copy selected cells/rows
- `Delete` — Trigger delete/deactivate flow (with guardrails)

## 4.3 Form shortcuts

- `Tab` / `Shift+Tab` — Next/previous field
- `Ctrl+Enter` — Submit form (if valid)
- `Alt+Down` — Open combo/list field
- `Ctrl+Z` / `Ctrl+Y` — Undo/redo field edits (where feasible)

### Shortcut policy

- Reserve OS-standard combinations.
- Never overload a shortcut for multiple actions in same context.
- Provide conflict-safe platform variations for macOS if supported.

---

## 5) Validation Behavior

Apply **layered validation**: input-level -> field-level -> form-level -> server/domain.

## 5.1 Input and field validation

- Validate format as user types for constrained fields (email, numeric, date).
- Validate semantic constraints on blur (required, range, pattern, uniqueness pre-check).
- Show message next to field; never only in toast.

## 5.2 Form submission validation

- On submit, validate all fields and section-level rules.
- Scroll to first invalid field and move focus there.
- Provide error summary banner at top with anchor links.

## 5.3 Server/domain validation

- Surface domain conflicts inline when possible (e.g., version conflict, business rule violation).
- Preserve user input after error; do not clear form.
- Distinguish:
  - **Correctable error** (user action needed)
  - **System error** (retry/contact support)

## 5.4 Validation language standards

- Message format: `What happened` + `How to fix`.
- Avoid technical jargon in user-facing copy.
- Include field labels in messages.

---

## 6) Empty, Loading, and Error States

Treat states as first-class UX components.

## 6.1 Empty states

Differentiate these types:

1. **First-use empty** (no data yet)
   - Explain value and show primary CTA (e.g., "Create customer").
2. **Filtered empty** (no results due to filters)
   - Show "Clear filters" quick action.
3. **Permission empty** (no access)
   - Explain restricted scope and next step.

Each empty state should include:
- concise title,
- plain-language explanation,
- one primary action,
- optional secondary help link.

## 6.2 Loading states

- **Initial page load:** skeleton placeholders for grids/forms.
- **Action load (save/submit):** disable relevant action button + inline progress indicator.
- **Background refresh:** subtle non-blocking progress in toolbar/footer.
- Show deterministic states; avoid indefinite spinner without status text.

## 6.3 Error states

### Recoverable errors

- Inline message near failed component.
- Offer immediate retry action.

### Non-recoverable errors

- Full-page error panel with reference ID and support path.
- Keep navigation available so user can continue elsewhere.

### Network interruptions

- Show offline banner.
- Queue safe retryable actions where possible.
- Prevent unsafe duplicate submissions.

---

## 7) Data Grid Standards

Grids are core to admin workflows; optimize for scanability and batch operations.

## 7.1 Grid structure

- Sticky header, optional sticky first column.
- Row height options: Comfortable / Compact.
- Zebra striping optional; prioritize clear selection styling.
- Right-align numeric and currency columns.
- Monospace for identifiers if helpful (order IDs, hashes).

## 7.2 Column behavior

- Resizable columns with saved user preferences.
- Reorderable columns (persist per user + module).
- Sort by one or multiple columns.
- Show truncation with tooltip on hover/focus.

## 7.3 Filtering and search

- Quick filter row for common fields.
- Advanced filter builder with AND/OR groups.
- Saved views (private + shared).
- Explicit indicator when filters are active.

## 7.4 Selection and bulk actions

- Checkbox selection column always first.
- Show selected count and contextual bulk action bar.
- Bulk actions require preview/impact summary.

## 7.5 Pagination and virtualization

- Use server-side pagination for large datasets.
- Provide page size options (e.g., 25/50/100).
- For very large pages, use row virtualization.

## 7.6 Grid status line

- Show total records, filtered count, last refreshed timestamp.
- Include export and refresh controls.

---

## 8) Form Standards

Forms must balance data density with readability.

## 8.1 Layout

- Max width for readability; use 1-2 column form layout.
- Group related fields into labeled sections/cards.
- Keep destructive actions visually separated.

## 8.2 Field design

- Labels always visible (no placeholder-only labels).
- Mark required fields with consistent token (`*`) and legend.
- Show helper text below field where needed.
- Disable, hide, or read-only states must be semantically distinct.

## 8.3 Stateful form behavior

- Dirty-state tracking with unsaved changes indicator.
- Autosave optional for low-risk forms; manual save for high-risk transactions.
- Optimistic UI only for reversible operations.

## 8.4 Form actions

- Primary actions right-aligned in footer: Save, Save & Close.
- Secondary actions: Cancel, Reset, Duplicate (contextual).
- Confirmation dialog for destructive or irreversible actions.

## 8.5 Complex/relational inputs

- Use pickers with typeahead for foreign keys.
- For inline child records, prefer embedded mini-grid with explicit add/remove.
- Validate cross-field dependencies in real time when feasible.

---

## 9) Dialog, Notification, and Feedback Standards

## 9.1 Dialogs

- Use dialogs for focused tasks; avoid multi-step wizard in modal unless necessary.
- Max 1 primary action + 1 destructive + 1 secondary.
- `Esc` closes non-destructive dialogs.

## 9.2 Notifications

- **Toast:** transient success/info, non-critical.
- **Inline alert:** actionable warnings/errors tied to context.
- **Notification center item:** background job outcomes and alerts requiring later review.

## 9.3 Action feedback timing

- Acknowledge user action within 100ms (visual state change).
- If operation >500ms, show progress indicator.
- If operation >10s, provide cancellable/background option where safe.

---

## 10) Accessibility and Internationalization Baseline

- Full keyboard navigation for all actionable controls.
- Visible focus ring with sufficient contrast.
- Support 200% UI scaling without loss of function.
- Avoid color-only meaning; include icon/text cues.
- Prepare layouts for longer localized strings.
- Use locale-aware date, number, and currency formatting.

---

## 11) PySide6 Implementation Notes (Practical)

- Define reusable base widgets:
  - `AppTableView`, `AppForm`, `AppDialog`, `StatusBanner`, `EmptyStatePanel`.
- Centralize theme tokens (spacing, typography, colors) in one style system.
- Use `QSortFilterProxyModel` for client-side filter/sort where dataset allows.
- For enterprise-scale grids, prefer model/view patterns with server-backed models.
- Standardize message boxes and toast manager via shared UX utility module.

---

## 12) UX Governance Checklist

Every new screen should pass this checklist before release:

1. Has defined empty/loading/error states.
2. Supports keyboard navigation and documented shortcuts.
3. Uses standard grid/form patterns.
4. Provides inline validation and submit summary.
5. Handles unsaved changes safely.
6. Includes permission-aware UI behavior.
7. Logs significant user actions for auditability (where policy allows).

This checklist ensures UX consistency as modules scale.
