"""Long-running scheduler for daily ingest (IST).

    python -m app.ingest.scheduler
"""

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.ingest import bhavcopy, compute_metrics, equity_list

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def daily():
    bhavcopy.load_latest()
    compute_metrics.run()


def main():
    sched = BlockingScheduler(timezone="Asia/Kolkata")
    # Bhavcopy is usually published by ~18:30 IST; retry at 21:00 in case it's late.
    sched.add_job(daily, CronTrigger(day_of_week="mon-fri", hour="19,21", minute=0), id="daily")
    sched.add_job(equity_list.main, CronTrigger(day_of_week="sun", hour=9, minute=0), id="equity_list")
    logging.info("Scheduler started")
    sched.start()


if __name__ == "__main__":
    main()
