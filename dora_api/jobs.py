"""The in-process scheduled jobs, as a table.

`bootstrap()` used to wire these inline — 80 lines and six function-level
imports (finalisation 19-R19). Listing them here as data means the boot log
can print the table (FU-720's cheapest shape) and a new job is one row.

Single-worker contract: the scheduler runs in exactly one process (see
`gunicorn.conf.py`), so every job fires once. The household-local jobs are
registered **hourly** and gate on the household clock internally (R-021) —
the cron fires in the *server's* timezone and the household timezone is a
runtime AppSetting, so a Settings change takes effect the same day instead of
at the next restart. Each push/email job self-gates when VAPID / SMTP isn't
configured, so an unconfigured install spends one cheap check per fire.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.base import BaseTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from dora_api.features.alerts.send_alerts_push import send_alerts_push
from dora_api.features.alerts.send_daily_brief import send_daily_brief
from dora_api.features.audit.prune_audit_events import prune_audit_events
from dora_api.features.deals.send_deals_email import send_deals_email
from dora_api.features.suggestions.prune_expired_snoozes import \
    prune_expired_snoozes
from dora_api.infrastructure.configuration_manager import DORA_CONFIG
from dora_api.persistence.seed_showcase import reset_showcase

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Job:
    id: str
    func: Callable[[], object]
    trigger: BaseTrigger
    why: str


# Minutes are staggered on purpose: :00 audit prune (03:00), :30 snooze prune
# (03:30), :30 alerts push, :45 daily brief, :15 deals email.
JOBS: tuple[Job, ...] = (
    Job("audit_retention", prune_audit_events, CronTrigger(hour=3, minute=0),
        "nightly audit-log retention sweep, clear of the household-evening sends"),
    Job("suggestions_snooze_cleanup", prune_expired_snoozes, CronTrigger(hour=3, minute=30),
        "daily prune of elapsed suggestion snoozes (off the read path, FU-513)"),
    Job("alerts_push", send_alerts_push, CronTrigger(minute=30),
        "hourly alerts web-push; self-gates without VAPID"),
    Job("daily_brief", send_daily_brief, CronTrigger(minute=45),
        "hourly, lands at 19:00 household time; self-gates without VAPID"),
    Job("deals_email", send_deals_email, CronTrigger(minute=15),
        "hourly, per-subscriber household-local weekday; self-gates without SMTP (FU-789)"),
)


def demo_reset_job() -> Job | None:
    """Demo / sellable-showcase auto-reset (FU-392): wipe + re-seed the
    curated showcase on a fixed interval so anyone poking at the demo starts
    clean. `DORA_DEMO_RESET_MINUTES=0` disables the reset (the boot-time seed
    still runs), leaving a static demo."""
    if not DORA_CONFIG.is_demo_mode_enabled():
        return None
    minutes = DORA_CONFIG.get_demo_reset_minutes()
    if minutes <= 0:
        return None
    return Job("demo_reset", reset_showcase, IntervalTrigger(minutes=minutes),
               f"demo showcase reset every {minutes} min")


def register_jobs(scheduler: BaseScheduler) -> list[Job]:
    """Add every job to `scheduler` and log the table once so a boot log
    shows what will fire and when."""
    jobs = list(JOBS)
    demo = demo_reset_job()
    if demo is not None:
        jobs.append(demo)
    for job in jobs:
        scheduler.add_job(job.func, job.trigger, id=job.id, replace_existing=True)
    _LOGGER.info(
        "Scheduled %d job(s): %s", len(jobs),
        "; ".join(f"{job.id} [{job.trigger}]" for job in jobs),
    )
    return jobs
