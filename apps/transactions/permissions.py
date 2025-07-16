from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied
import logging

logger = logging.getLogger(__name__)

class AccountTypePermission(BasePermission):
  
    required_account_types = []
    
    def has_permission(self, request, view):
        
        if not request.user or not request.user.is_authenticated:
            logger.warning(" User not authenticated")
            return False
        
        
        user_account_type = getattr(request, 'user_account_type', None)
        
        if not user_account_type:
            logger.warning(f" user_account_type not found in request for user {request.user.id}")
            return False
        
        
        if hasattr(view, 'required_account_types'):
            required_types = view.required_account_types
        else:
            required_types = self.required_account_types
        
      
        is_authorized = user_account_type in required_types
        
        if not is_authorized:
            logger.warning(
                f" Access denied for user {request.user.id} "
                f"(account_type: {user_account_type}, required: {required_types})"
            )
        else:
            logger.info(
                f" Access granted for user {request.user.id} "
                f"(account_type: {user_account_type})"
            )
        
        return is_authorized
    
    def has_object_permission(self, request, view, obj):
        
        return self.has_permission(request, view)


class PersonnelAccountPermission(AccountTypePermission):
    
    required_account_types = ['personnel']


class AgencyAccountPermission(AccountTypePermission):
    
    required_account_types = ['agency']


class BusinessAccountPermission(AccountTypePermission):
  
    required_account_types = ['business']


class MultipleAccountTypesPermission(AccountTypePermission):

    pass


class AgencyOrBusinessPermission(AccountTypePermission):
    
    required_account_types = ['agency', 'business']


class AllAccountTypesPermission(AccountTypePermission):
    
    required_account_types = ['personnel', 'business', 'agency']

