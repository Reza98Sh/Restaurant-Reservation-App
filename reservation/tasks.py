
from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


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

    if count:
        logger.info(f"Expired {count} pending reservations")

    return {"expired_count": count}
