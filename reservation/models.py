# apps/reservations/models.py

from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError


class PaymentRecord(models.Model):
    """
    Payment record model linked to Reservation.Automatically confirms reservation upon successful payment verification.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"
        FAILED = "failed", "Failed"

    reservation = models.ForeignKey(
        "reservation.Reservation", on_delete=models.PROTECT, related_name="payments"
    )

    amount = models.PositiveIntegerField()

    # Payment gateway reference
    ref_id = models.CharField(max_length=100, blank=True)

    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.PENDING
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["reservation", "status"]),
        ]

    def __str__(self):
        return f"Payment {self.id} - {self.reservation} - {self.status}"

    def verify(self, ref_id: str = ""):
        """
        Verify payment and confirm the linked reservation.
        """
        self.status = self.Status.VERIFIED
        self.ref_id = ref_id
        self.verified_at = timezone.now()
        self.save(update_fields=["status", "ref_id", "verified_at"])

        # Confirm the reservation
        self.reservation.confirm()

    def fail(self):
        """
        Mark payment as failed.
        """
        self.status = self.Status.FAILED
        self.save(update_fields=["status"])


class Reservation(models.Model):
    """
    Core reservation model.
    Now includes start_time and end_time directly instead of TimeSlot reference.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending Payment"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    user = models.ForeignKey(
        "users.CustomUser", on_delete=models.CASCADE, related_name="reservations"
    )
    table = models.ForeignKey(
        "restaurant.Table", on_delete=models.CASCADE, related_name="reservations"
    )

    # Reservation details - date and time
    date = models.DateField()
    start_time = models.TimeField(help_text="Reservation start time")
    end_time = models.TimeField(help_text="Reservation end time")

    guest_count = models.PositiveIntegerField()

    price = models.PositiveIntegerField()

    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.PENDING
    )

    # Payment deadline for pending reservations
    payment_deadline = models.DateTimeField(null=True, blank=True)

    cancellation_reason = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-start_time"]
        indexes = [
            models.Index(fields=["date", "status"]),
            models.Index(fields=["date", "start_time", "end_time"]),
            models.Index(fields=["table", "date", "start_time"]),
        ]

    def __str__(self):
        return f" {self.user} - {self.date} ({self.start_time}-{self.end_time})"

    def clean(self):
        """
        Validate reservation constraints.
        """
        super().clean()

        # Validate end_time > start_time
        if self.start_time and self.end_time:
            if self.end_time <= self.start_time:
                raise ValidationError(
                    {"end_time": "End time must be after start time."}
                )

        # VIP table: only one reservation per day
        if self.table and self.date:
            if self.table.table_type == "VIP":
                existing = Reservation.objects.filter(
                    table=self.table,
                    date=self.date,
                    status__in=[self.Status.PENDING, self.Status.CONFIRMED],
                )
                # Exclude self when updating
                if self.pk:
                    existing = existing.exclude(pk=self.pk)

                if existing.exists():
                    raise ValidationError(
                        {"table": "VIP tables can only have one reservation per day."}
                    )

    def save(self, *args, **kwargs):

        # Run validation
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def duration_minutes(self):
        """
        Calculate reservation duration in minutes.
        """
        from datetime import datetime, date

        # Create datetime objects for calculation
        start_dt = datetime.combine(date.today(), self.start_time)
        end_dt = datetime.combine(date.today(), self.end_time)

        delta = end_dt - start_dt
        return int(delta.total_seconds() / 60)

    def set_payment_deadline(self, minutes: int = 15):
        """
        Set payment deadline based on reservation type.
        Normal reservations: 15 minutes
        Waitlist reservations: 30 minutes
        """
        self.payment_deadline = timezone.now() + timedelta(minutes=minutes)
        self.save(update_fields=["payment_deadline"])

    def is_payment_expired(self) -> bool:
        """Check if payment deadline has passed."""
        if self.payment_deadline:
            return timezone.now() > self.payment_deadline
        return False

    def confirm(self):
        """Confirm the reservation after successful payment."""
        self.status = self.Status.CONFIRMED
        self.payment_deadline = None
        self.save(update_fields=["status", "payment_deadline", "updated_at"])

    def cancel(self, reason: str = ""):
        """Handle reservation cancellation."""
        self.status = self.Status.CANCELLED
        self.cancellation_reason = reason
        self.save(update_fields=["status", "cancellation_reason", "updated_at"])

    def complete(self):
        """Mark reservation as completed."""
        self.status = self.Status.COMPLETED
        self.save(update_fields=["status", "updated_at"])


class WaitlistEntry(models.Model):
    """
    Waitlist model for tracking users waiting for a specific table/time slot.
    """

    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        NOTIFIED = "notified", "Notified"  
        CONVERTED = "converted", "Converted to Reservation"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled by User"

    user = models.ForeignKey(
        "users.CustomUser", on_delete=models.CASCADE, related_name="waitlist_entries"
    )
    table = models.ForeignKey(
        "restaurant.Table", on_delete=models.CASCADE, related_name="waitlist_entries"
    )

    # Desired reservation details
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    guest_count = models.PositiveIntegerField()

    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.WAITING
    )

    # Position in queue (lower = higher priority)
    position = models.PositiveIntegerField(default=0)

    # When user was notified
    notified_at = models.DateTimeField(null=True, blank=True)

    # Deadline to complete payment after notification
    payment_deadline = models.DateTimeField(null=True, blank=True)

    # Reference to created reservation (if converted)
    reservation = models.OneToOneField(
        Reservation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="waitlist_source",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date", "start_time", "position"]
        indexes = [
            models.Index(fields=["table", "date", "start_time", "status"]),
            models.Index(fields=["user", "status"]),
        ]
        # Prevent duplicate waitlist entries for same user/table/time
        unique_together = ("user", "table", "date", "start_time", "end_time")

    def __str__(self):
        return f"Waitlist: {self.user} - {self.table} - {self.date} ({self.start_time}-{self.end_time})"

    def clean(self):
        """
        Validate that end_time is after start_time.
        """
        super().clean()
        if self.start_time and self.end_time:
            if self.end_time <= self.start_time:
                raise ValidationError(
                    {"end_time": "End time must be after start time."}
                )

    def notify(self):
        """Mark entry as notified and set payment deadline."""
        self.status = self.Status.NOTIFIED
        self.notified_at = timezone.now()
        self.payment_deadline = timezone.now() + timedelta(minutes=30)
        self.save(
            update_fields=["status", "notified_at", "payment_deadline", "updated_at"]
        )

    def convert_to_reservation(self, reservation: Reservation):
        """Convert waitlist entry to actual reservation."""
        self.status = self.Status.CONVERTED
        self.reservation = reservation
        self.save(update_fields=["status", "reservation", "updated_at"])

    def expire(self):
        """Mark entry as expired."""
        self.status = self.Status.EXPIRED
        self.save(update_fields=["status", "updated_at"])

    def cancel(self):
        """Cancel waitlist entry."""
        self.status = self.Status.CANCELLED
        self.save(update_fields=["status", "updated_at"])



