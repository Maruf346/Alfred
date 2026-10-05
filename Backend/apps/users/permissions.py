"""
Custom DRF permission classes for the users app.
"""

from rest_framework.permissions import BasePermission


class IsSubscribed(BasePermission):
    """
    Allow access only to users on Monthly or Annual subscription plans.
    """

    message = "This feature requires an active subscription (Monthly or Annual)."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_subscribed
        )


class IsSubscribedMonthly(BasePermission):
    """
    Allow access only to users on Monthly subscription plans.
    """

    message = "This feature requires an active Monthly subscription."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_subscribed_monthly()
        )


class IsSubscribedAnnual(BasePermission):
    """
    Allow access only to users on Annual subscription plans.
    """

    message = "This feature requires an active Annual subscription."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_subscribed_annual()
        )


class IsAdminUser(BasePermission):
    """
    Allow access only to authenticated platform administrators.
    """

    message = "Admin access required."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_admin
        )
