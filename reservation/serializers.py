from django.utils import timezone
from rest_framework import serializers

from restaurant.models import Restaurant
from restaurant import models as restaurant_models
from reservation.models import Reservation, PaymentRecord


class CancelReservationSerializer(serializers.Serializer):
    """
    Serializer for cancellation request.
    """

    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Optional reason for cancellation",
    )


class TableReserveSerializer(serializers.ModelSerializer):
    """
    Serializer for table reservation requests.
    Validation logic is now handled by ReservationService.
    """

    class Meta:
        model = Reservation
        fields = [
            "id",
            "table",
            "date",
            "start_time",
            "end_time",
            "guest_count",
            "user",
            "price",
            "status",
        ]
        read_only_fields = ["id", "user", "price", "status"]


class TableAvailabilitySerializer(serializers.ModelSerializer):
    """
    Serializer for table availability response
    """

    price = serializers.IntegerField()

    class Meta:
        model = restaurant_models.Table
        fields = [
            "id",
            "restaurant",
            "number",
            "price",
            "capacity",
            "reservations",
            "table_type",
        ]


class AvailabilityQuerySerializer(serializers.Serializer):
    """
    Serializer for validating availability query parameters.
    Automatically sets default values for date and time if not provided.
    """

    restaurant = serializers.IntegerField(required=True)
    date = serializers.DateField(required=False, allow_null=True)
    start_time = serializers.TimeField(required=False, allow_null=True)
    end_time = serializers.TimeField(required=False, allow_null=True)
    number_of_people = serializers.IntegerField(required=False, default=1, min_value=1)

    def validate_restaurant(self, value):
        """
        Validate that the restaurant exists.
        """
        try:
            # Store restaurant instance for later use in validate method
            self._restaurant = Restaurant.objects.get(pk=value)
        except Restaurant.DoesNotExist:
            raise serializers.ValidationError("Restaurant not found.")
        return value

    def validate(self, attrs):
        """
        Set default values for date and time based on restaurant's operating hours.
        - If date is not provided, use today's date
        - If start_time is not provided, use restaurant's opening_time
        - If end_time is not provided, use restaurant's closing_time
        """
        # Get the restaurant instance (already validated in validate_restaurant)
        restaurant = self._restaurant

        # Set default date to today if not provided
        if not attrs.get("date"):
            attrs["date"] = timezone.localdate()

        # Set default start_time to restaurant's opening_time if not provided
        if not attrs.get("start_time"):
            attrs["start_time"] = restaurant.opening_time

        # Set default end_time to restaurant's closing_time if not provided
        if not attrs.get("end_time"):
            attrs["end_time"] = restaurant.closing_time

        # Validate that start_time is before end_time
        if attrs["start_time"] >= attrs["end_time"]:
            raise serializers.ValidationError(
                {"end_time": "End time must be after start time."}
            )

        # Validate that requested time is within restaurant's operating hours
        if attrs["start_time"] < restaurant.opening_time:
            raise serializers.ValidationError(
                {"start_time": f"Restaurant opens at {restaurant.opening_time}."}
            )

        if attrs["end_time"] > restaurant.closing_time:
            raise serializers.ValidationError(
                {"end_time": f"Restaurant closes at {restaurant.closing_time}."}
            )

        # Validate that date is not in the past
        if attrs["date"] < timezone.localdate():
            raise serializers.ValidationError(
                {"date": "Cannot check availability for past dates."}
            )

        return attrs


class PaymentVerifySerializer(serializers.Serializer):
    """
    Serializer for verifying a payment.
    """

    ref_id = serializers.CharField(max_length=100, required=False, default="")




class PaymentRecordSerializer(serializers.ModelSerializer):
    """
    Serializer for PaymentRecord model.
    Includes nested reservation details.
    """

    # Nested reservation info
    reservation = TableReserveSerializer(read_only=True)

    # Human-readable status
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = PaymentRecord
        fields = [
            "id",
            "reservation",
            "amount",
            "ref_id",
            "status",
            "status_display",
            "created_at",
            "verified_at",
        ]
        read_only_fields = fields
