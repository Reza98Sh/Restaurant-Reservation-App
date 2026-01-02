from django.db.models import (
    F,
    Q,
    When,
    Case,
    Value,
    Exists,
    Prefetch,
    QuerySet,
    OuterRef,
    IntegerField,
    ExpressionWrapper,
)
from datetime import date, time

from reservation.models import Reservation
from restaurant.models import Table


class TableAvailabilityService:
    """
    Service class for handling table availability logic.
    """

    @staticmethod
    def round_up_to_even(number: int) -> int:
        """
        Round up number of people to even number
        Example: 3 -> 4, 5 -> 6, 4 -> 4
        """
        if number % 2 == 0:
            return number
        return number + 1

    @staticmethod
    def _get_overlap_base_query(
        check_date: date, start_time: time, end_time: time
    ) -> QuerySet:
        """
        Internal helper to generate the base QuerySet for overlapping reservations.
        This defines the core logic of what constitutes a conflict.
        """
        return Reservation.objects.filter(
            date=check_date,
            status__in=[Reservation.Status.PENDING, Reservation.Status.CONFIRMED],
        ).filter(
            # Two time ranges overlap if: start1 < end2 AND start2 < end1
            Q(start_time__lt=end_time)
            & Q(end_time__gt=start_time)
        )

    @classmethod
    def check_specific_table_availability(
        cls,
        table: Table,
        check_date: date,
        start_time: time,
        end_time: time,
    ) -> bool:
        """
        Check if a SPECIFIC table is available.
        Reusable method to be called by ReservationService.
        """
        # Get the base conflict query
        conflicting_query = cls._get_overlap_base_query(
            check_date, start_time, end_time
        )

        # Filter for the specific table
        conflicting_query = conflicting_query.filter(table=table)

        # If conflicts exist, table is NOT available
        return not conflicting_query.exists()

    @classmethod
    def get_available_tables(
        cls,
        restaurant_id: int,
        check_date: date,
        start_time: time,
        end_time: time,
        party_size: int,
    ):
        """
        Get all tables with their reservations for a specific date and time range.
        """
        seats_needed = cls.round_up_to_even(party_size)

        base_overlap_query = cls._get_overlap_base_query(
            check_date, start_time, end_time
        )

        overlapping_reservations = base_overlap_query.filter(table=OuterRef("pk"))

        # Prefetch reservations for the specific date to show in response
        reservations_for_date = Prefetch(
            "reservations",
            queryset=Reservation.objects.filter(
                date=check_date, status__in=["pending", "confirmed"]
            ).order_by("start_time"),
            to_attr="day_reservations",
        )

        # Calculate seat price based on table type
        seat_price_annotation = Case(
            When(
                table_type=Table.TableType.VIP,
                then=F("restaurant__vip_price_per_seat"),
            ),
            default=F("restaurant__normal_price_per_seat"),
            output_field=IntegerField(),
        )

        # Calculate full table price: (capacity - 1) * seat_price
        table_price = ExpressionWrapper(
            (F("capacity") - Value(1)) * seat_price_annotation,
            output_field=IntegerField(),
        )

        tables = (
            Table.objects.filter(
                restaurant_id=restaurant_id, capacity__gte=seats_needed
            )
            .prefetch_related(reservations_for_date)
            .annotate(
                # Check if table has overlapping reservation (True = has conflict)
                has_reservation=Exists(overlapping_reservations),
                seat_price=seat_price_annotation,
                price=table_price,
            )
            .order_by("has_reservation", "price", "capacity")
        )

        return tables
