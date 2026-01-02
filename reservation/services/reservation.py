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
    def check_table_availability(
        table: Table,
        date: datetime.date,
        start_time: time,
        end_time: time,
        exclude_reservation_id: Optional[int] = None,
    ) -> bool:
        """
        Check if a table is available for the given time slot.
        Returns True if available, False otherwise.
        """
        # Query for conflicting reservations
        conflicting_query = Reservation.objects.filter(
            table=table,
            date=date,
            status__in=[Reservation.Status.PENDING, Reservation.Status.CONFIRMED],).filter(
            # Time overlap check: existing reservation overlaps with requested time
            Q(start_time__lt=end_time) & Q(end_time__gt=start_time)
        )

        # Exclude current reservation if updating
        if exclude_reservation_id:
            conflicting_query = conflicting_query.exclude(id=exclude_reservation_id)

        return not conflicting_query.exists()

    @staticmethod
    def validate_guest_count(table: Table, guest_count: int) -> Tuple[bool, str]:
        """
        Validate that guest count doesn't exceed table capacity.
        Returns (is_valid, error_message) tuple.
        """
        if guest_count > table.capacity:
            return (
                False,
                f"تعداد مهمان‌ها ({guest_count}) بیشتر از ظرفیت میز ({table.capacity}) است."
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
            status=PaymentRecord.Status.PENDING
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
        from_waitlist: bool = False,
    ) -> Tuple[Optional[Reservation], str]:
        """
        Create a new reservation if table is available.
        Also creates associated PaymentRecord.
        
        Note: Pending reservations will be automatically expired by the
        periodic task 'expire_stale_pending_reservations' if payment is
        not completed within 10 seconds.
        
        Returns (reservation, message) tuple.
        """
        # Validate guest count against table capacity
        is_valid, error_message = cls.validate_guest_count(table, guest_count)
        if not is_valid:
            return None, error_message

        # Check availability
        if not cls.check_table_availability(table, date, start_time, end_time):
            return None, "این میز در بازه زمانی انتخاب شده رزرو شده است."

        # Calculate price
        price = cls.calculate_price(table, guest_count)

        # Create reservation inside atomic transaction
        with transaction.atomic():
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
            deadline_minutes = 1  # For testing; change to 15 or 30 in production
            reservation.set_payment_deadline(deadline_minutes)

            # Create associated PaymentRecord
            cls._create_payment_record(reservation)
            
            # No need to schedule individual expiration task anymore!
            # The periodic task 'expire_stale_pending_reservations' handles this

        return (
            reservation,
            "رزرو با موفقیت ایجاد شد. لطفاً پرداخت را تکمیل کنید.",
        )

    @classmethod
    def cancel_reservation(
        cls, reservation: Reservation, reason: str = "", notify_waitlist: bool = True
    ) -> bool:
        """
        Cancel a reservation and optionally notify waitlist.
        """
        from reservation.tasks import process_waitlist_after_cancellation

        reservation.cancel(reason)

        if notify_waitlist:
            # Use on_commit to ensure cancellation is saved before task runs
            def trigger_waitlist_task():
                process_waitlist_after_cancellation.delay(
                    table_id=reservation.table_id,
                    date=reservation.date.isoformat(),
                    start_time=reservation.start_time.isoformat(),
                    end_time=reservation.end_time.isoformat(),
                )
            
            transaction.on_commit(trigger_waitlist_task)

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
