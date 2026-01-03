from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import generics, permissions, filters, status
from django_filters.rest_framework import DjangoFilterBackend

from reservation.services.availability import TableAvailabilityService
from reservation.serializers import (
    TableReserveSerializer,
    WaitlistEntrySerializer,
    PaymentRecordSerializer,
    PaymentVerifySerializer,
    TableAvailabilitySerializer,
    AvailabilityQuerySerializer,
    CancelReservationSerializer,
)
from reservation.models import Reservation, PaymentRecord, WaitlistEntry
from config import permissions
from reservation.services.reservation import ReservationService


class TableAvailabilityView(APIView):
    """
    API endpoint to check table availability for a specific date and time
    This is the MAIN endpoint for showing available tables
    """

    @extend_schema(
        parameters=[
            OpenApiParameter(name="restaurant", type=int, required=True),
            OpenApiParameter(name="date", type=str, description="Date (YYYY-MM-DD)"),
            OpenApiParameter(
                name="start_time", type=str, description="Start time (HH:MM)"
            ),
            OpenApiParameter(name="end_time", type=str, description="End time (HH:MM)"),
            OpenApiParameter(name="number_of_people", type=int),
        ],
        responses={200: TableAvailabilitySerializer(many=True)},
    )
    def get(self, request):
        """
        Get available tables for the specified criteria
        Returns all tables with their availability status,
        sorted by availability and price (cheapest first)
        """

        # Validate query parameters
        query_serializer = AvailabilityQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        data = query_serializer.validated_data

        # Get availability data
        available_tables = TableAvailabilityService.get_available_tables(
            restaurant_id=data["restaurant"],
            check_date=data["date"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            party_size=data["number_of_people"],
        )
        # Serialize response
        serializer = TableAvailabilitySerializer(available_tables, many=True)

        return Response(
            {
                "query": query_serializer.validated_data,
                "results": serializer.data,
            }
        )


class ReserveTableView(generics.CreateAPIView):
    """
    API view for creating table reservations.
    Uses ReservationService to handle reservation creation logic.
    """

    serializer_class = TableReserveSerializer
    queryset = Reservation.objects.all()
    permission_classes = [permissions.IsAuthenticatedUser]

    def create(self, request, *args, **kwargs):
        """
        Override create method to use ReservationService for reservation creation.
        """
        # Validate input data using serializer
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Extract validated data
        validated_data = serializer.validated_data

        # Use ReservationService to create reservation
        reservation, message = ReservationService.create_reservation(
            user=request.user,
            table=validated_data["table"],
            date=validated_data["date"],
            start_time=validated_data["start_time"],
            end_time=validated_data["end_time"],
            guest_count=validated_data["guest_count"],
        )

        # Check if reservation was created successfully
        if reservation is None:
            return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)

        # Serialize the created reservation for response
        output_serializer = self.get_serializer(reservation)

        return Response(
            {"detail": message, "reservation": output_serializer.data},
            status=status.HTTP_201_CREATED,
        )


class CancelReservationView(generics.GenericAPIView):
    """
    API endpoint to cancel an existing reservation.
    """

    serializer_class = CancelReservationSerializer
    permission_classes = [permissions.IsAuthenticatedUser]
    lookup_field = "pk"

    def get_queryset(self):
        """
        Ensure users can only interact with their own reservations.
        """
        return Reservation.objects.filter(user=self.request.user)

    @extend_schema(
        summary="Cancel a reservation",
        description="Cancels a pending or confirmed reservation. "
        "This action may trigger notifications to the waitlist.",
        responses={
            200: {"description": "Reservation cancelled successfully"},
            400: {
                "description": "Reservation cannot be cancelled (e.g. already completed)"
            },
            404: {"description": "Reservation not found or does not belong to user"},
        },
    )
    def post(self, request, *args, **kwargs):
        """
        Handle the cancellation request using POST method (Action pattern).
        """
        reservation = self.get_object()

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get("reason", "")
        
        if reservation.status in [
            Reservation.Status.CANCELLED,
            Reservation.Status.COMPLETED,
        ]:
            return Response(
                {
                    "detail": f"Cannot cancel reservation with status '{reservation.status}'."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


        success = ReservationService.cancel_reservation(
            reservation=reservation, reason=reason, notify_waitlist=True
        )

        if success:
            return Response(
                {"message": "Reservation cancelled successfully."},
                status=status.HTTP_200_OK,
            )
        else:
            # Fallback in case service returns False (though currently it returns True)
            return Response(
                {"detail": "Failed to cancel reservation."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class PaymentVerifyView(generics.GenericAPIView):
    """
    API endpoint to verify a payment and confirm reservation.
    """

    serializer_class = PaymentVerifySerializer
    permission_classes = [permissions.IsAuthenticatedUser]

    @extend_schema(
        summary="Verify payment",
        description="Verifies payment and automatically confirms the reservation.",
        responses={
            200: {"description": "Payment verified successfully"},
            400: {"description": "Already processed"},
            404: {"description": "Payment not found"},
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payment_id = serializer.validated_data["payment_id"]

        # Find pending payment for current user
        try:
            payment = PaymentRecord.objects.get(
                id=payment_id,
                status=PaymentRecord.Status.PENDING,
                reservation__user=request.user,
            )
            payment.verify()
            payment.reservation.confirm()
        except PaymentRecord.DoesNotExist:
            return Response(
                {"detail": "Payment not found or already processed."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {"message": "Payment verified and reservation confirmed."},
            status=status.HTTP_200_OK,
        )


class PaymentAccessMixin:
    permission_classes = [permissions.IsAuthenticatedUser]

    def get_queryset(self):
        """
        Return queryset based on user type:
        - Admin: All payment records with related data
        - Regular user: Only their own payment records
        """
        user = self.request.user

        # Base queryset with optimized related data loading
        queryset = PaymentRecord.objects.select_related(
            "reservation",
            "reservation__user",
            "reservation__table",
        )

        # Check if user is admin/staff
        if user.is_restaurant_staff or user.is_admin:
            # Admin can see all payments
            return queryset.all()
        else:
            # Regular user can only see their own payments
            return queryset.filter(reservation__user=user)


class PaymentListView(PaymentAccessMixin, generics.ListAPIView):
    """
    View to list payment records.
    """

    serializer_class = PaymentRecordSerializer
    # Enable filtering, searching, and ordering
    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter,
    ]

    # Fields that can be filtered
    filterset_fields = {
        "status": ["exact"],
        "created_at": ["gte", "lte", "date"],
        "verified_at": ["gte", "lte", "date"],
        "amount": ["gte", "lte", "exact"],
    }

    # Fields that can be used for ordering
    ordering_fields = ["created_at", "verified_at", "amount", "status"]
    ordering = ["-created_at"]  # Default ordering


class PaymentDetailView(
    PaymentAccessMixin,
    generics.RetrieveAPIView,
):
    """
    View to retrieve a single payment record detail.
    """

    serializer_class = PaymentRecordSerializer


class WaitlistEntryCreateView(generics.CreateAPIView):
    """
    API endpoint for creating a new waitlist entry.
    """

    queryset = WaitlistEntry.objects.all()
    serializer_class = WaitlistEntrySerializer
    permission_classes = [permissions.IsAuthenticatedUser]
