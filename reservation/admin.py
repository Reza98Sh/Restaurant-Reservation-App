# apps/reservations/admin.py

from django.contrib import admin
from django.utils.html import format_html
from .models import Reservation, WaitlistEntry, PaymentRecord


@admin.register(PaymentRecord)
class PaymentRecordAdmin(admin.ModelAdmin):
    """
    Admin configuration for PaymentRecord model.
    """
    list_display = (
        'id',
        'ref_id',
        'status_badge',
        'created_at',
        'verified_at',
    )
    list_filter = ('status', 'created_at', 'verified_at')
    search_fields = (
        'ref_id',
        'reservation__user__username',
        'reservation__user__email',
        'reservation__table__restaurant__name',)
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'verified_at')
    list_select_related = ('reservation', 'reservation__user', 'reservation__table')

    # Raw ID field for better performance with many reservations
    raw_id_fields = ('reservation',)

    fieldsets = (
        ('Payment Information', {
            'fields': ('reservation', 'amount', 'status')
        }),
        ('Gateway Details', {
            'fields': ('ref_id',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'verified_at'),
            'classes': ('collapse',)
        }),
    )



    def status_badge(self, obj):
        """
        Display status as colored badge.
        """
        colors = {
            'pending': '#f0ad4e',   # Orange/Yellow for pending
            'verified': '#5cb85c',  # Green for verified
            'failed': '#d9534f',    # Red for failed
        }
        color = colors.get(obj.status, '#777')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    # Admin actions
    actions = ['mark_as_verified', 'mark_as_failed']

    @admin.action(description='Mark selected payments as verified')
    def mark_as_verified(self, request, queryset):
        """
        Bulk action to verify payments.
        Note: This uses the model's verify method to also confirm reservations.
        """
        count = 0
        for payment in queryset.filter(status=PaymentRecord.Status.PENDING):
            payment.verify(ref_id='ADMIN_VERIFIED')
            count += 1
        self.message_user(request, f'{count} payment(s) marked as verified.')

    @admin.action(description='Mark selected payments as failed')
    def mark_as_failed(self, request, queryset):
        """
        Bulk action to mark payments as failed.
        """
        count = 0
        for payment in queryset.filter(status=PaymentRecord.Status.PENDING):
            payment.fail()
            count += 1
        self.message_user(request, f'{count} payment(s) marked as failed.')


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    """
    Admin configuration for Reservation model.
    """
    list_display = (
        'user',
        'table',
        'date',
        'guest_count',
        'price',
        'status_badge',
        'created_at'
    )
    list_filter = ('status', 'date', 'table__restaurant', 'table__table_type')
    search_fields = (
        'user__username',
        'user__email', 
        'table__restaurant__name'
    )
    ordering = ('-date', '-start_time')
    date_hierarchy = 'date'
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('user', 'table', 'table__restaurant')

    # Raw ID fields for better performance with many users/tables
    raw_id_fields = ('user', 'table')

    fieldsets = (
        ('Tracking', {
            'fields': ('status',)
        }),
        ('Reservation Details', {
            'fields': ('user', 'table', 'date', 'start_time', 'end_time', 'guest_count', 'price')
        }),
        ('Payment', {
            'fields': ('payment_deadline',),
            'classes': ('collapse',)
        }),
        ('Cancellation', {
            'fields': ('cancellation_reason',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def status_badge(self, obj):
        """
        Display status as colored badge.
        """
        colors = {
            'pending': '#f0ad4e',
            'confirmed': '#5cb85c',
            'cancelled': '#d9534f',
            'completed': '#5bc0de',
            'expired': '#BA68C8',
        }
        color = colors.get(obj.status, '#777')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    # Admin actions
    actions = ['mark_as_confirmed', 'mark_as_cancelled', 'mark_as_completed']

    @admin.action(description='Mark selected reservations as confirmed')
    def mark_as_confirmed(self, request, queryset):
        """
        Bulk action to confirm reservations.
        """
        updated = queryset.update(status=Reservation.Status.CONFIRMED)
        self.message_user(request, f'{updated} reservation(s) marked as confirmed.')

    @admin.action(description='Mark selected reservations as cancelled')
    def mark_as_cancelled(self, request, queryset):
        """
        Bulk action to cancel reservations.
        """
        updated = queryset.update(status=Reservation.Status.CANCELLED)
        self.message_user(request, f'{updated} reservation(s) marked as cancelled.')

    @admin.action(description='Mark selected reservations as completed')
    def mark_as_completed(self, request, queryset):
        """
        Bulk action to complete reservations.
        """
        updated = queryset.update(status=Reservation.Status.COMPLETED)
        self.message_user(request, f'{updated} reservation(s) marked as completed.')


@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin):
    """
    Admin configuration for WaitlistEntry model.
    """
    list_display = (
        'id',
        'user',
        'table',
        'date',
        'guest_count',
        'status_badge',
        'notified_at'
    )
    list_filter = ('status', 'date', 'table__restaurant')
    search_fields = (
        'user__username', 
        'user__email',
        'table__restaurant__name'
    )
    ordering = ('date', 'start_time',)
    date_hierarchy = 'date'
    list_select_related = ('user', 'table', 'table__restaurant', 'reservation')

    # Raw ID fields for better performance
    raw_id_fields = ('user', 'table', 'reservation')

    fieldsets = (
        ('User & Table', {
            'fields': ('user', 'table')
        }),
        ('Waitlist Details', {
            'fields': ('date', 'start_time', 'end_time', 'guest_count',  'status')
        }),
        ('Notification', {
            'fields': ('notified_at',),
            'classes': ('collapse',)
        }),
        ('Conversion', {
            'fields': ('reservation',),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('notified_at', 'created_at', 'updated_at')

    def status_badge(self, obj):
        """
        Display status as colored badge.
        """
        colors = {
            'waiting': '#5bc0de',
            'notified': '#f0ad4e',
            'converted': '#5cb85c',
            'expired': '#d9534f',
            'cancelled': '#777777',
        }
        color = colors.get(obj.status, '#777')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    # Admin actions
    actions = ['notify_users', 'mark_as_expired', 'mark_as_cancelled']

    @admin.action(description='Notify selected waitlist entries')
    def notify_users(self, request, queryset):
        """
        Bulk action to notify waitlist users.
        """
        count = 0
        for entry in queryset.filter(status=WaitlistEntry.Status.WAITING):
            entry.notify()
            count += 1
        self.message_user(request, f'{count} user(s) notified.')

    @admin.action(description='Mark selected entries as expired')
    def mark_as_expired(self, request, queryset):
        """
        Bulk action to expire waitlist entries.
        """
        updated = queryset.update(status=WaitlistEntry.Status.EXPIRED)
        self.message_user(request, f'{updated} entry(ies) marked as expired.')

    @admin.action(description='Mark selected entries as cancelled')
    def mark_as_cancelled(self, request, queryset):
        """
        Bulk action to cancel waitlist entries.
        """
        updated = queryset.update(status=WaitlistEntry.Status.CANCELLED)
        self.message_user(request, f'{updated} entry(ies) marked as cancelled.')
