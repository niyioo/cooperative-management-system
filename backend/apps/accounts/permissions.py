from rest_framework.permissions import BasePermission

class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'SUPER_ADMIN')

class IsManagerOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in ['SUPER_ADMIN', 'MANAGER'])

class IsLoanOfficer(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in ['SUPER_ADMIN', 'MANAGER', 'LOAN_OFFICER'])
    
class IsOwnerOrManager(BasePermission):
    """
    Allows a member to view/edit their own Member record, 
    but allows Managers/Super Admins to view/edit anyone's.
    """
    def has_object_permission(self, request, view, obj):
        # First, ensure they are logged in
        if not (request.user and request.user.is_authenticated):
            return False
            
        # Managers and Admins can access any object
        if request.user.role in ['SUPER_ADMIN', 'MANAGER']:
            return True
            
        # Ensure the regular member is only accessing their own data
        return obj.user == request.user