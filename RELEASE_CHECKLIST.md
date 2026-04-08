# Desktop Application Release Checklist

Use this checklist for production releases of a professional desktop application.

## 1) Release Readiness & Scope
- [ ] Confirm release version, build number, and release date/time window.
- [ ] Freeze scope: list included features, bug fixes, and known exclusions.
- [ ] Verify issue tracker status (all release-blocking tickets resolved or explicitly waived).
- [ ] Confirm release owner, incident commander, and approvers.
- [ ] Share go/no-go criteria with engineering, QA, product, and support.

## 2) Database/Data Migrations
- [ ] Inventory all schema/data/config migrations included in this release.
- [ ] Validate forward migration in a staging environment with production-like data.
- [ ] Validate backward compatibility of app against pre- and post-migration states (if required).
- [ ] Estimate migration runtime and acceptable downtime window.
- [ ] Confirm migration idempotency/retry behavior and failure handling.
- [ ] Prepare manual migration fallback steps (if automation fails).
- [ ] Capture migration logs and success markers for release evidence.

## 3) Backup & Rollback Plan
- [ ] Take verified backups/snapshots of critical data stores before rollout.
- [ ] Validate backup integrity with a test restore (not just backup creation).
- [ ] Document rollback trigger thresholds (error rate, crash rate, install failures, etc.).
- [ ] Document exact rollback sequence (application binaries, migrations, config, feature flags).
- [ ] Confirm ownership and communication channel for rollback decision.
- [ ] Timebox rollback execution and recovery objectives (RTO/RPO).
- [ ] Stage previous stable installer/package for immediate redeploy.

## 4) Secrets, Certificates, and Environment Security
- [ ] Confirm no secrets are hardcoded in source, config, logs, or installer payload.
- [ ] Rotate/revalidate release-time secrets/tokens where policy requires.
- [ ] Verify production secret access scopes are least-privilege.
- [ ] Confirm code-signing certificate validity and expiration window.
- [ ] Verify timestamping service availability for signing workflow.
- [ ] Validate secure storage of signing keys (HSM/key vault) and access auditability.
- [ ] Confirm environment variables and endpoint URLs are correct per environment.

## 5) Build, Packaging, and Signed Installer Validation
- [ ] Build reproducible release artifacts from tagged commit.
- [ ] Verify artifact checksums and provenance metadata.
- [ ] Sign executables/installers and verify signature chain/trust on target OSes.
- [ ] Confirm notarization/stapling requirements (if applicable) are completed.
- [ ] Run clean-machine install/upgrade/uninstall tests for each supported platform.
- [ ] Validate installer UX: prerequisites, disk-space checks, permissions prompts, and downgrade behavior.
- [ ] Run malware/AV reputation checks as required by policy.

## 6) Smoke Test Suite (Post-Build and Post-Deploy)
- [ ] Launch app from fresh install and verify first-run flow.
- [ ] Validate login/authentication and session persistence.
- [ ] Validate core user journeys (top 5 business-critical workflows).
- [ ] Validate data read/write and sync behavior (online/offline where relevant).
- [ ] Validate crash reporting/telemetry emission.
- [ ] Validate auto-update channel and update prompt behavior.
- [ ] Validate license/subscription checks (if applicable).

## 7) Accessibility Review
- [ ] Re-run accessibility checks for key flows (keyboard-only navigation, focus order, visible focus).
- [ ] Validate screen reader labels/roles/states for critical controls.
- [ ] Verify color contrast and non-color status indicators.
- [ ] Validate text scaling/high-DPI behavior and responsive layout stability.
- [ ] Validate reduced-motion and other OS accessibility preferences are respected.
- [ ] Confirm accessibility regressions are documented with severity and remediation plan.

## 8) User Acceptance Testing (UAT)
- [ ] Confirm UAT plan and acceptance criteria are signed off by product/business stakeholders.
- [ ] Execute UAT scenarios for priority personas/use cases.
- [ ] Capture UAT defects, triage severity, and define release disposition.
- [ ] Obtain formal UAT sign-off (named approver + timestamp).
- [ ] Archive UAT evidence (test notes, recordings, screenshots, reports).

## 9) Release Execution & Communications
- [ ] Announce rollout window and customer impact (if any).
- [ ] Enable phased rollout/canary ring with monitoring guardrails.
- [ ] Track live KPIs: install success, startup crash-free rate, API error rate, support ticket volume.
- [ ] Run go/no-go checkpoint at each release phase.
- [ ] Publish release notes (customer-facing and internal technical notes).

## 10) Support Handover & Hypercare
- [ ] Prepare support runbook: known issues, workarounds, escalation paths, severity matrix.
- [ ] Share release notes and troubleshooting FAQ with support/success teams.
- [ ] Confirm on-call schedule and escalation contacts for first 24-72 hours.
- [ ] Provide diagnostic collection instructions for support engineers.
- [ ] Define hypercare duration and daily review cadence.
- [ ] Track post-release incidents and feed learnings into next release retrospective.

## 11) Final Sign-off Record
- [ ] Engineering sign-off
- [ ] QA sign-off
- [ ] Security sign-off
- [ ] Product sign-off
- [ ] Support readiness sign-off
- [ ] Final go-live approval logged with date/time and approver names

---

## Optional Release Evidence Template
- Release version/tag:
- Commit SHA:
- Build artifact IDs/checksums:
- Migration execution ID/log location:
- Backup snapshot ID and restore verification evidence:
- Signed installer verification output:
- Smoke test report link:
- Accessibility report link:
- UAT sign-off link:
- Support handover doc link:
- Go-live decision log link:
