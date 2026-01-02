# apps/accounts/permissions.py

from rest_framework import permissions


class IsAdminUser(permissions.BasePermission):
    """
    Permission class that only allows admin users.
    """
    message = 'Only admin users can perform this action.'
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.is_admin
        )


class IsManagerOrAdmin(permissions.BasePermission):
    """
    Permission class that allows managers and admins.
    Used for: Branch management, Table management, Menu management.
    """
    message = 'Only managers and admins can perform this action.'
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.has_role('manager', 'admin')


class IsStaffOrAbove(permissions.BasePermission):
    """
    Permission class that allows staff, managers, and admins.
    Used for: Viewing reservations, Order management.
    """
    message = 'Only staff members can perform this action.'
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.has_role('staff', 'manager', 'admin')


class IsOwnerOrStaff(permissions.BasePermission):
    """
    Permission class that allows object owners or staff members.
    Used for: Viewing/Canceling own reservations.
    """
    message = 'You can only access your own resources.'
    
    def has_object_permission(self, request, view, obj):
        # Staff and above can access any object
        if request.user.has_role('staff', 'manager', 'admin'):
            return True
        
        # Check if user owns the object
        if hasattr(obj, 'user'):
            return obj.user == request.user
        if hasattr(obj, 'customer'):
            return obj.customer == request.user
        
        return False


class IsAuthenticatedUser(permissions.BasePermission):
    """
    Permission class for authenticated customers.
    Used for: Making reservations, Placing orders.
    """
    message = 'Authentication is required for this action.'
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.is_active
        )



