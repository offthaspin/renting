# scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import date, datetime
from sqlalchemy.exc import IntegrityError
from rentme.models import JobLock
import pytz
import logging

from rentme.models import auto_update_all_unpaid_rents
from rentme.extensions import db

# --------------------------------------------------
# Timezone
# --------------------------------------------------
KENYA_TZ = pytz.timezone("Africa/Nairobi")

# --------------------------------------------------
# Logger
# --------------------------------------------------
logger = logging.getLogger("rentme.scheduler")
logger.setLevel(logging.INFO)

# --------------------------------------------------
# Scheduler (DEFINED ONLY — NEVER AUTO-START)
# --------------------------------------------------
scheduler = BackgroundScheduler(timezone=KENYA_TZ)


def monthly_rent_update():
    """
    DB-LOCKED monthly rent updater.
    GUARANTEED to run only once per month.
    """
    today = date.today()
    job_name = "monthly_rent_update"

    logger.info("🔐 Attempting DB lock for monthly rent update")

    try:
        # Try to acquire lock
        lock = JobLock.query.filter_by(job_name=job_name).with_for_update().first()

        if not lock:
            lock = JobLock(job_name=job_name)
            db.session.add(lock)
            db.session.flush()

        # If already run this month → EXIT
        if lock.last_run == today.replace(day=1):
            logger.info("⏭ Monthly rent already updated — skipping")
            return

        # Lock job
        lock.locked_at = datetime.utcnow()
        db.session.commit()

        logger.info("🔓 Lock acquired — running rent update")

        # --- ACTUAL JOB ---
        auto_update_all_unpaid_rents()

        # Mark success
        lock.last_run = today.replace(day=1)
        lock.locked_at = None

        db.session.commit()

        logger.info("✅ Monthly rent update completed and locked")

    except IntegrityError:
        db.session.rollback()
        logger.warning("⚠️ Another worker acquired the lock first — exiting")

    except Exception:
        db.session.rollback()
        logger.exception("❌ Monthly rent update failed")
        raise


def configure_scheduler():
    """
    Register scheduler jobs ONLY.
    Does NOT start the scheduler.
    """
    trigger = CronTrigger(
        day=1,
        hour=2,
        minute=0,
        timezone=KENYA_TZ,
    )

    scheduler.add_job(
        func=monthly_rent_update,
        trigger=trigger,
        id="monthly_rent_update",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,  # 1 hour safety window
    )

    logger.info("📅 Scheduler jobs configured (not started)")


def start_scheduler():
    """
    Start scheduler explicitly.
    USE ONLY IN:
    - Background worker
    - Local development
    NEVER from Flask app startup.
    """
    if scheduler.running:
        logger.warning("⚠️ Scheduler already running — start skipped")
        return

    configure_scheduler()
    scheduler.start()
    logger.info("🕓 Scheduler started — monthly rent updates ACTIVE")
