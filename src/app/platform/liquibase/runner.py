from __future__ import annotations

import logging
import shlex
import subprocess

logger = logging.getLogger(__name__)


class LiquibaseError(RuntimeError):
    """Raised when Liquibase execution fails."""


def maybe_run_liquibase(
    *,
    enabled: bool,
    command: str,
    changelog_file: str,
    contexts: str,
    labels: str | None,
) -> None:
    """Safe startup checkpoint.

    This should run *before* DB sessions are used and before UI launches.
    """
    if not enabled:
        logger.info("Liquibase disabled; skipping migration step")
        return

    cmd_parts = [
        *shlex.split(command),
        f"--changelog-file={changelog_file}",
        f"--contexts={contexts}",
    ]
    if labels:
        cmd_parts.append(f"--labels={labels}")
    cmd_parts.append("update")

    logger.info("Running Liquibase before app startup")
    result = subprocess.run(cmd_parts, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        logger.error("Liquibase failed: %s", result.stderr.strip())
        raise LiquibaseError("Liquibase update failed. Aborting app startup.")

    logger.info("Liquibase completed successfully")
