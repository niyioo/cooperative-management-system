from rest_framework.permissions import BasePermission

# Role groups, used by permissions and by querysets that decide who sees what.
MANAGERS = ('SUPER_ADMIN', 'MANAGER')
FINANCE_STAFF = ('SUPER_ADMIN', 'MANAGER', 'ACCOUNTANT')
LOAN_STAFF = ('SUPER_ADMIN', 'MANAGER', 'LOAN_OFFICER')
# Everyone who may record a payment received from a member.
PAYMENT_STAFF = ('SUPER_ADMIN', 'MANAGER', 'ACCOUNTANT', 'LOAN_OFFICER')
STAFF = PAYMENT_STAFF


def has_role(user, roles) -> bool:
    return bool(user and user.is_authenticated and user.is_active and user.role in roles)


class _RolePermission(BasePermission):
    roles = ()

    def has_permission(self, request, view):
        return has_role(request.user, self.roles)


class IsSuperAdmin(_RolePermission):
    roles = ('SUPER_ADMIN',)


class IsManagerOrAdmin(_RolePermission):
    roles = MANAGERS


class IsFinanceStaff(_RolePermission):
    roles = FINANCE_STAFF


class IsLoanOfficer(_RolePermission):
    roles = LOAN_STAFF


class IsPaymentStaff(_RolePermission):
    roles = PAYMENT_STAFF


class IsStaff(_RolePermission):
    roles = STAFF


class IsOwnerOrManager(BasePermission):
    """
    Allows a member to view/edit their own Member record,
    but allows Managers/Super Admins to view/edit anyone's.
    """
    def has_object_permission(self, request, view, obj):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.role in MANAGERS:
            return True
        return obj.user == request.user
