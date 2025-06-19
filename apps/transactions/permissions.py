# from rest_framework.permissions import BasePermission
# import logging

# logger = logging.getLogger(__name__)

# class AccountTypePermission(BasePermission):
#     required_account_types = []
    
#     def has_permission(self, request, view):
        
        
#         if not request.user or not request.user.is_authenticated:
#             print("❌ User not authenticated")
#             return False
      
#         user_account_type = getattr(request, 'user_account_type', None)
        
#         if not user_account_type:
#             print("❌ user_account_type not found in request")
#             return False
        
#         if hasattr(view, 'required_account_types'):
#             required_types = view.required_account_types
#         else:
#             required_types = self.required_account_types
        
#         result = user_account_type in required_types
        
#         return result

# class PersonnelAccountPermission(AccountTypePermission):
#     required_account_types = ['personnel']

# class AgencyAccountPermission(AccountTypePermission):
#     required_account_types = ['agency']

# class ComercantAccountPermission(AccountTypePermission):
#     required_account_types = ['business']