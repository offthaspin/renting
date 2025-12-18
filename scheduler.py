# scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import date
import pytz
import logging

from rentme.models import auto_update_all_unpaid_rents
from rentme.extensions import db

# Kenya timezone (EAT)
KENYA_TZ = pytz.timezone("Africa/Nairobi")

logger = logging.getLogger(__name__)

# Scheduler is defined, but NEVER auto-started
scheduler = BackgroundScheduler(timezone=KENYA_TZ)


def monthly_rent_update():
    """
    Job that auto-updates unpaid rent balances.
    SAFE to run via cron / CLI.
    """
    today = date.today()
    logger.info("🏠 Running monthly rent update — %s [Kenya Time]", today)

    try:
        auto_update_all_unpaid_rents()
        db.session.commit()
        logger.info("✅ Rent balances updated successfully.")
    except Exception:
        logger.exception("❌ Error during rent update")
        db.session.rollback()
        raise


def configure_scheduler():
    """
    Configure scheduler jobs WITHOUT starting it.
    (Never auto-start in production)
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
    )


def start_scheduler():
    """
    Start scheduler explicitly.
    USE ONLY in development or a dedicated worker.
    NEVER call on app startup in production.
    """
    if scheduler.running:
        logger.warning("Scheduler already running — skipping start.")
        return

    configure_scheduler()
    scheduler.start()
    logger.info("🕓 Scheduler started — monthly rent updates enabled.")
