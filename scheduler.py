# scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import date
import pytz
from models import auto_update_all_unpaid_rents
from extensions import db

# Kenya timezone (EAT)
kenya_tz = pytz.timezone("Africa/Nairobi")

scheduler = BackgroundScheduler(timezone=kenya_tz)

def monthly_rent_update():
    """Job that auto-updates unpaid rent balances every month (Kenya time)."""
    print(f"🏠 Running monthly rent update — {date.today()} [Kenya Time]")
    try:
        auto_update_all_unpaid_rents()
        db.session.commit()
        print("✅ Rent balances updated successfully.")
    except Exception as e:
        print(f"❌ Error during rent update: {e}")
        db.session.rollback()

def start_scheduler():
    """Start background scheduler (runs once per month)."""
    # Runs every 1st day of the month at 2:00 AM (Kenya time)
    trigger = CronTrigger(day=1, hour=2, minute=0, timezone=kenya_tz)
    scheduler.add_job(monthly_rent_update, trigger)
    scheduler.start()
    print("🕓 Scheduler started — updates unpaid rent every 1st of the month (Kenya time).")
