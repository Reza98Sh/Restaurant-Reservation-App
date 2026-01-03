# reservation/services/reservation.py

from django.db import transaction
from django.db.models import Q
from datetime import datetime, time
from typing import Optional, Tuple
from decimal import Decimal

from reservation.models import Reservation, PaymentRecord
from restaurant.models import Table
from users.models import CustomUser


class ReservationService:
    """
    Service class for handling reservation logic.
    """

    @staticmethod
    def validate_guest_count(table: Table, guest_count: int) -> Tuple[bool, str]:
        """
        Validate that guest count doesn't exceed table capacity.
        Returns (is_valid, error_message) tuple.
        """
        if guest_count > table.capacity:
            return (
                False,
                f"Guest count ({guest_count}) exceeds table capacity ({table.capacity}).",
            )
        return True, ""

    @staticmethod
    def calculate_price(table: Table, guest_count: int) -> Decimal:
        """
        Calculate reservation price based on table and guest count.
        """
        return table.restaurant.normal_price_per_seat * guest_count

    @classmethod
    def _create_payment_record(cls, reservation: Reservation) -> PaymentRecord:
        """
        Create a PaymentRecord for the given reservation.
        This is a private method called within the transaction.
        """
        return PaymentRecord.objects.create(
            reservation=reservation,
            amount=reservation.price,
            status=PaymentRecord.Status.PENDING,
        )

    @classmethod
    def create_reservation(
        cls,
        user: CustomUser,
        table: Table,
        date: datetime.date,
        start_time: time,
        end_time: time,
        guest_count: int,
    ) -> Tuple[Optional[Reservation], str]:
        """
        Create a new reservation if table is available.
        Also creates associated PaymentRecord.

        Note: Pending reservations will be automatically expired by the
        periodic task 'expire_stale_pending_reservations' if payment is
        not completed within the allowed time.

        Returns (reservation, message) tuple.
        """
        # Validate guest count against table capacity
        is_valid, error_message = cls.validate_guest_count(table, guest_count)
        if not is_valid:
            return None, error_message

        from reservation.services.availability import TableAvailabilityService

        # Create reservation inside atomic transaction
        with transaction.atomic():
            # Check availability
            if not TableAvailabilityService.check_specific_table_availability(
                table, date, start_time, end_time
            ):
                return None, "This table is already reserved."

            # Calculate price
            price = cls.calculate_price(table, guest_count)

            # Create reservation
            reservation = Reservation.objects.create(
                user=user,
                table=table,
                date=date,
                start_time=start_time,
                end_time=end_time,
                guest_count=guest_count,
                price=price,
                status=Reservation.Status.PENDING,
            )

            # Set payment deadline
            deadline_minutes = 15
            reservation.set_payment_deadline(deadline_minutes)

            # Create associated PaymentRecord
            cls._create_payment_record(reservation)

        return (
            reservation,
            "Reservation created successfully. Please complete the payment.",
        )

    @classmethod
    def cancel_reservation(
        cls, reservation: Reservation, reason: str = "", notify_waitlist: bool = True
    ) -> bool:
        """
        Cancel a reservation and optionally notify waitlist.
        """
        # Store slot info before cancellation
        table = reservation.table
        date = reservation.date
        start_time = reservation.start_time
        end_time = reservation.end_time

        # Cancel the reservation
        reservation.cancel(reason)

        from reservation.services.waitlist import WaitlistService

        entry = WaitlistService.process_waitlist(
            table=table,
            date=date,
            start_time=start_time,
            end_time=end_time,
        )

        if entry:
            reservation, _ = cls.create_reservation(
                user=entry.user,
                date=entry.date,
                table=entry.table,
                start_time=entry.start_time,
                end_time=entry.end_time,
                guest_count=entry.guest_count,
            )
            entry.convert_to_reservation(reservation)

        return True

    @classmethod
    def confirm_reservation(cls, reservation: Reservation) -> bool:
        """
        Confirm reservation after successful payment.
        """
        if reservation.status != Reservation.Status.PENDING:
            return False

        if reservation.is_payment_expired():
            reservation.mark_expired()
            return False

        reservation.confirm()
        return True
