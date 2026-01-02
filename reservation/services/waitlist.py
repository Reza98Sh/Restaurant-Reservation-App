from django.db import transaction
from django.db.models import (
    Q,
)
from django.utils import timezone
from datetime import datetime, time
from typing import Optional, Tuple

from reservation.models import Reservation, WaitlistEntry
from restaurant.models import Table
from users.models import CustomUser
from reservation.services.availability import TableAvailabilityService
from reservation.services.reservation import ReservationService


class WaitlistService:
    """
    Service class for handling waitlist logic.
    """

    @staticmethod
    def get_next_position(table: Table, date: datetime.date, start_time: time) -> int:
        """Get the next position number for waitlist queue."""
        last_entry = (
            WaitlistEntry.objects.filter(
                table=table,
                date=date,
                start_time=start_time,
                status=WaitlistEntry.Status.WAITING,
            )
            .order_by("-position")
            .first()
        )

        return (last_entry.position + 1) if last_entry else 1

    @classmethod
    @transaction.atomic
    def add_to_waitlist(
        cls,
        user: CustomUser,
        table: Table,
        date: datetime.date,
        start_time: time,
        end_time: time,
        guest_count: int,
    ) -> Tuple[Optional[WaitlistEntry], str]:
        """
        Add user to waitlist for a specific table/time.
        """
        # Check if user already in waitlist for this slot
        existing = WaitlistEntry.objects.filter(
            user=user,
            table=table,
            date=date,
            start_time=start_time,
            status__in=[WaitlistEntry.Status.WAITING, WaitlistEntry.Status.NOTIFIED],
        ).exists()

        if existing:
            return None, "You are already on the waitlist for this table."

        # Validate guest count
        if guest_count > table.capacity:
            return (
                None,
                f"Number of guests ({guest_count}) exceeds table capacity ({table.capacity}).",
            )
        # Get position in queue
        position = cls.get_next_position(table, date, start_time)

        # Create waitlist entry
        entry = WaitlistEntry.objects.create(
            user=user,
            table=table,
            date=date,
            start_time=start_time,
            end_time=end_time,
            guest_count=guest_count,
            position=position,
        )

        return entry, f"You have been added to the waitlist at position {position}."

    @classmethod
    def get_first_waiting_entry(
        cls, table: Table, date: datetime.date, start_time: time, end_time: time
    ) -> Optional[WaitlistEntry]:
        """
        Get the first waiting entry for a specific table/time slot.
        Checks for time overlap to find matching waitlist entries.
        """
        return (
            WaitlistEntry.objects.filter(
                table=table, date=date, status=WaitlistEntry.Status.WAITING
            )
            .filter(
                # Time overlap: waitlist entry time overlaps with available slot
                Q(start_time__lt=end_time)
                & Q(end_time__gt=start_time)
            )
            .order_by("position", "created_at")
            .first()
        )

    @classmethod
    @transaction.atomic
    def process_waitlist_for_slot(
        cls, table: Table, date: datetime.date, start_time: time, end_time: time
    ) -> Optional[WaitlistEntry]:
        """
        Process waitlist when a slot becomes available.
        Returns the notified entry or None.
        """
        from reservation.tasks import (
            expire_waitlist_entry,
        )

        # Get first waiting entry
        entry = cls.get_first_waiting_entry(table, date, start_time, end_time)

        if not entry:
            return None

        # Mark as notified
        entry.notify()
    

        # Schedule expiration check after 30 minutes
        expire_waitlist_entry.apply_async(
            args=[entry.id], countdown=30 * 60  # 30 minutes in seconds
        )

        return entry

    @classmethod
    @transaction.atomic
    def convert_waitlist_to_reservation(
        cls, entry: WaitlistEntry
    ) -> Tuple[Optional[Reservation], str]:
        """
        Convert a notified waitlist entry to a reservation.
        """
        # Validate entry status
        if entry.status != WaitlistEntry.Status.NOTIFIED:
            return None, "This request is no longer valid."

        # Check if payment deadline passed
        if entry.payment_deadline and timezone.now() > entry.payment_deadline:
            entry.expire()
            return None, "Payment deadline has passed."

        # Check table availability again (safety check)
        if not TableAvailabilityService.check_specific_table_availability(
            entry.table, entry.date, entry.start_time, entry.end_time
        ):
            return None, "This table is no longer available."

        # Create reservation
        reservation, message = ReservationService.create_reservation(
            user=entry.user,
            table=entry.table,
            date=entry.date,
            start_time=entry.start_time,
            end_time=entry.end_time,
            guest_count=entry.guest_count,
            from_waitlist=True,
        )

        if reservation:
            entry.convert_to_reservation(reservation)
            return (
                reservation,
                "Reservation created successfully. Please complete the payment.",
            )

        return None, message
