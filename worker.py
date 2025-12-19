"""
Background worker for Rentana
Runs scheduled jobs ONLY ONCE (safe for production)
"""

from rentme.app import create_app
from rentme.scheduler import start_scheduler

app = create_app()

if __name__ == "__main__":
    start_scheduler()

    # Keep process alive
    import time
    while True:
        time.sleep(60)
