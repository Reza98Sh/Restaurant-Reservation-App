# reservation/tasks.py

from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_waitlist_for_slot(self, table_id: int, date: str, start_time: str, end_time: str):
    """
    Process waitlist after a slot becomes available.
    """
    from datetime import datetime
    from restaurant.models import Table
    from reservation.services.waitlist import WaitlistService

    try:
        table = Table.objects.get(id=table_id)
        entry = WaitlistService.process_waitlist_for_slot(
            table=table,
            date=datetime.fromisoformat(date).date(),
            start_time=datetime.strptime(start_time, "%H:%M:%S").time(),
            end_time=datetime.strptime(end_time, "%H:%M:%S").time(),
        )

        if entry:
            logger.info(f"Notified waitlist entry {entry.id} for table {table_id}")
            return {"status": "notified", "entry_id": entry.id}

        return {"status": "no_waitlist"}

    except Exception as exc:
        logger.error(f"Error processing waitlist: {exc}")
        raise self.retry(exc=exc)


@shared_task
def expire_pending_reservations():
    """
    Periodic task: Expire reservations past their payment deadline.
    Run every minute via Celery Beat.
    """
    from reservation.models import Reservation

    now = timezone.now()
    expired_reservations = Reservation.objects.filter(
        status=Reservation.Status.PENDING,
        payment_deadline__lt=now,
    )

    count = 0
    for reservation in expired_reservations:
        reservation.mark_expired()
        count += 1

        # Trigger waitlist for freed slot
        process_waitlist_for_slot.delay(
            table_id=reservation.table_id,
            date=reservation.date.isoformat(),
            start_time=reservation.start_time.isoformat(),
            end_time=reservation.end_time.isoformat(),
        )

    if count:
        logger.info(f"Expired {count} pending reservations")

    return {"expired_count": count}



