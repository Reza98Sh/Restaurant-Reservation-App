# apps/restaurant/admin.py

from django.contrib import admin
from .models import Restaurant, Table


class TableInline(admin.TabularInline):
    """
    Inline admin for tables within restaurant admin page.
    """
    model = Table
    extra = 1
    fields = ('number', 'table_type', 'capacity')


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    """
    Admin configuration for Restaurant model.
    """
    list_display = ('name', 'phone', 'opening_time', 'closing_time', 'vip_price_per_seat', 'normal_price_per_seat')
    list_filter = ('opening_time', 'closing_time')
    search_fields = ('name', 'address', 'phone')
    ordering = ('name',)
    
    # Include tables as inline
    inlines = [TableInline]
    
    fieldsets = (
        (None, {
            'fields': ('name', 'address', 'phone')
        }),
        ('Pricing', {
            'fields': ('vip_price_per_seat', 'normal_price_per_seat')
        }),
        ('Operating Hours', {
            'fields': ('opening_time', 'closing_time')
        }),
    )


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    """
    Admin configuration for Table model.
    """
    list_display = ('number', 'restaurant', 'table_type', 'capacity')
    list_filter = ('table_type', 'restaurant')
    search_fields = ('restaurant__name', 'number')
    ordering = ('restaurant', 'number')
    list_select_related = ('restaurant',)
