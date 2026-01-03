# apps/accounts/models.py

from django.contrib.auth.models import AbstractUser, PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class CustomUser(AbstractUser, PermissionsMixin):
    """
    Custom User model using email as the unique identifier instead of username.
    Supports role-based access control for restaurant management system.
    """

    class Role(models.TextChoices):
        """
        User roles enumeration for role-based access control.
        """
        CUSTOMER = 'customer', _('Customer')
        STAFF = 'staff', _('Staff')
        MANAGER = 'manager', _('Manager')
        ADMIN = 'admin', _('Admin')

    # Role and permissions
    role = models.CharField(
        _('role'),
        max_length=20,
        choices=Role.choices,
        default=Role.CUSTOMER,
        db_index=True,
        help_text=_('User role for access control.')
    )

    # Timestamps
    date_joined = models.DateTimeField(
        _('date joined'),
        default=timezone.now
    )


    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['email', 'role']),
            models.Index(fields=['is_active', 'role']),
        ]

    def __str__(self):
        return self.username

    # Role checking properties

    @property
    def is_customer(self):
        """Check if user is a customer."""
        return self.role == self.Role.CUSTOMER

    @property
    def is_restaurant_staff(self):
        """Check if user is restaurant staff."""
        return self.role == self.Role.STAFF

    @property
    def is_manager(self):
        """Check if user is a manager."""
        return self.role == self.Role.MANAGER

    @property
    def is_admin(self):
        """Check if user is an admin."""
        return self.role == self.Role.ADMIN

    def has_role(self, *roles):
        """
        Check if user has any of the specified roles.
        """
        return self.role in roles
