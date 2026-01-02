# reservation/tasks.py

from celery import shared_task
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_waitlist_after_cancellation(
    self,
    table_id: int,
    date: str,
    start_time: str,
    end_time: str
):
    """
    Process waitlist after a reservation is cancelled.
    Finds the first waiting user and notifies them.
    """
    from restaurant.models import Table
    from reservation.services.waitlist import WaitlistService

    try:
        table = Table.objects.get(id=table_id)
        date_obj = datetime.fromisoformat(date).date()
        start_time_obj = datetime.strptime(start_time, '%H:%M:%S').time()
        end_time_obj = datetime.strptime(end_time, '%H:%M:%S').time()

        entry = WaitlistService.process_waitlist_for_slot(
            table=table,
            date=date_obj,
            start_time=start_time_obj,
            end_time=end_time_obj
        )

        if entry:
            logger.info(f"Waitlist entry {entry.id} notified for table {table_id}")
            return {'status': 'notified', 'entry_id': entry.id}
        else:
            logger.info(f"No waitlist entries for table {table_id} at {date} {start_time}")
            return {'status': 'no_waitlist'}

    except Exception as exc:
        logger.error(f"Error processing waitlist: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True)
def expire_waitlist_entry(self, waitlist_entry_id: int):
    """
    Expire a waitlist entry if payment was not completed in time.
    Then process the next person in waitlist.
    """
    from .models import WaitlistEntry, Reservation
    from reservation.services.waitlist import WaitlistService

    try:
        entry = WaitlistEntry.objects.select_related('table').get(
            id=waitlist_entry_id
        )

        # Check if still in NOTIFIED status (not yet paid)
        if entry.status != WaitlistEntry.Status.NOTIFIED:
            logger.info(f"Waitlist entry {waitlist_entry_id} already processed: {entry.status}")
            return {'status': 'already_processed'}

        # Check if associated reservation exists and is still pending
        if entry.reservation:
            if entry.reservation.status == Reservation.Status.PENDING:
                # Expire the reservation too
                entry.reservation.mark_expired()
                logger.info(f"Expired reservation {entry.reservation.id}")

        # Expire the waitlist entry
        entry.expire()
        logger.info(f"Expired waitlist entry {waitlist_entry_id}")

        # Process next person in waitlist
        next_entry = WaitlistService.process_waitlist_for_slot(
            table=entry.table,
            date=entry.date,
            start_time=entry.start_time,
            end_time=entry.end_time
        )

        if next_entry:
            return {
                'status': 'expired_and_next_notified',
                'expired_entry_id': waitlist_entry_id,
                'next_entry_id': next_entry.id
            }

        return {'status': 'expired', 'entry_id': waitlist_entry_id}

    except WaitlistEntry.DoesNotExist:
        logger.error(f"Waitlist entry {waitlist_entry_id} not found")
        return {'status': 'not_found'}
    except Exception as exc:
        logger.error(f"Error expiring waitlist entry: {exc}")
        return {'status': 'error', 'message': str(exc)}


@shared_task
def expire_stale_pending_reservations():
    """
    Periodic task to expire PENDING reservations older than 10 seconds.
    This task runs every minute via Celery Beat.
    
    It finds all reservations that:
    - Have status = PENDING
    - Were created more than 10 seconds ago
    Then cancels them and triggers waitlist processing for each.
    """
    from .models import Reservation

    expired_count = 0
    now = timezone.now()
    
    # Calculate the cutoff time (10 seconds ago)
    cutoff_time = now - timedelta(seconds=10)

    # Find all pending reservations created before the cutoff time
    stale_reservations = Reservation.objects.filter(
        status=Reservation.Status.PENDING,
        created_at__lt=cutoff_time
    )

    for reservation in stale_reservations:
        # Cancel the reservation with a reason
        reservation.cancel(reason="Payment not completed within time limit")
        expired_count += 1
        
        logger.info(
            f"Expired stale reservation {reservation.id} "
            f"(created at {reservation.created_at}, age: {now - reservation.created_at})"
        )

        # Trigger waitlist processing for the freed slot
        process_waitlist_after_cancellation.delay(
            table_id=reservation.table_id,
            date=reservation.date.isoformat(),
            start_time=reservation.start_time.isoformat(),
            end_time=reservation.end_time.isoformat()
        )

    logger.info(f"Expired {expired_count} stale pending reservations")
    return {'expired_count': expired_count}


@shared_task
def expire_pending_reservations():
    """
    Periodic task to expire reservations that have passed their payment deadline.
    Should run every minute.
    
    Note: This is different from expire_stale_pending_reservations.
    This one checks payment_deadline field, while the other checks created_at.
    """
    from .models import Reservation

    expired_count = 0
    now = timezone.now()

    # Find all pending reservations past their deadline
    pending_reservations = Reservation.objects.filter(
        status=Reservation.Status.PENDING,
        payment_deadline__lt=now
    )

    for reservation in pending_reservations:
        reservation.mark_expired()
        expired_count += 1

        # If this was from waitlist, the waitlist entry expiration
        # will be handled by expire_waitlist_entry task
        if not reservation.from_waitlist:
            # For normal reservations, trigger waitlist processing
            process_waitlist_after_cancellation.delay(
                table_id=reservation.table_id,
                date=reservation.date.isoformat(),
                start_time=reservation.start_time.isoformat(),
                end_time=reservation.end_time.isoformat()
            )

    logger.info(f"Expired {expired_count} pending reservations")
    return {'expired_count': expired_count}


@shared_task
def check_and_complete_reservations():
    """
    Periodic task to mark reservations as completed after their end time.
    Should run every 15 minutes.
    """
    from .models import Reservation

    now = timezone.now()
    today = now.date()
    current_time = now.time()

    # Find confirmed reservations that have ended
    completed_count = 0
    reservations = Reservation.objects.filter(
        status=Reservation.Status.CONFIRMED,
        date__lte=today
    )

    for reservation in reservations:
        # Check if reservation has ended
        if reservation.date < today or (
            reservation.date == today and reservation.end_time <= current_time
        ):
            reservation.complete()
            completed_count += 1

    logger.info(f"Completed {completed_count} reservations")
    return {'completed_count': completed_count}
