from rest_framework.permissions import BasePermission

class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.role == 'SUPER_ADMIN')

class IsManagerOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.role in ['SUPER_ADMIN', 'MANAGER'])

class IsLoanOfficer(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.role in ['SUPER_ADMIN', 'MANAGER', 'LOAN_OFFICER'])