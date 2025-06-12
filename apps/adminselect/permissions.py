from rest_framework import permissions
from django.contrib.auth.models import Group

class RoleBasedPermission(permissions.BasePermission):
    """
    Permission personnalisée basée sur les rôles utilisateur
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Récupérer la base de données utilisée
        bank_db = getattr(request, 'source_bank_db', 'default')
        print(bank_db)
        # Vérifier que l'utilisateur existe dans cette base de données
        try:
            from apps.users.models import User
            db_user = User.objects.using(bank_db).get(id=request.user.id)
        except User.DoesNotExist:
            return False
            
        # Récupérer le rôle de l'utilisateur dans cette base de données
        user_groups = db_user.groups.using(bank_db).values_list('name', flat=True)
        print("Groupes de l'utilisateur:", list(user_groups))
        
        # Admin a accès à tout
        if 'admin' in user_groups:
            return True
            
        # Mapping des permissions par vue et rôle
        permission_map = {
            'RegistrationAcounteAgancyBisenessView': {
                'admin': ['POST'],  # AJOUTÉ
                'backoffice': ['POST'],
                'business': ['POST'],
                'agency': ['POST'],
                'kyc': [],
                'reporting': ['GET']
            },
            
            # Vues Transaction
            'TransactionViewSet': {
                'admin': ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],  # AJOUTÉ
                'backoffice': ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
                'business': [],
                'agency': [],
                'kyc': [],
                'reporting': ['GET']
            },
            
            # Vues Account
            'AccountViewSet': {
                'admin': ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],  # AJOUTÉ
                'backoffice': ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
                'business': ['GET', 'PUT', 'PATCH'],  # Gestion business
                'agency': ['GET', 'PUT', 'PATCH'],    # Gestion agence
                'kyc': ['GET', 'PUT', 'PATCH'],       # Validation compte
                'reporting': ['GET']
            },
            
            # Vues FeeRule (sensible - tarifs)
            'FeeRuleViewSet': {
                'admin': ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],  # AJOUTÉ
                'backoffice': [],  # Pas d'accès aux tarifs
                'business': [],
                'agency': [],
                'kyc': [],
                'reporting': ['GET']
            },
            
            # Vues Fee (sensible)
            'FeeViewSet': {
                'admin': ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],  # AJOUTÉ
                'backoffice': [],
                'business': [],
                'agency': [],
                'kyc': [],
                'reporting': ['GET']
            },
            
            # Vues PaymentRequest
            'PaymentRequestViewSet': {
                'admin': ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],  # AJOUTÉ
                'backoffice': ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
                'business': ['GET', 'POST', 'PUT', 'PATCH'],
                'agency': [],
                'kyc': [],
                'reporting': ['GET']
            },
            
            # Vues PreTransaction
            'PreTransactionViewSet': {
                'admin': ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],  # AJOUTÉ
                'backoffice': ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
                'business': [],
                'agency': ['GET', 'POST'],
                'kyc': [],
                'reporting': ['GET']
            },
            
            # Vues DemandeChequiers
            'DemandeChequiersViewSet': {
                'admin': ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],  # AJOUTÉ
                'backoffice': ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
                'business': ['GET', 'POST'],
                'agency': ['GET', 'POST', 'PUT', 'PATCH'],
                'kyc': [],
                'reporting': ['GET']
            },
            
            # Vues Dashboard
            'DashboardViewSet': {
                'admin': ['GET'],  # AJOUTÉ
                'backoffice': ['GET'],
                'business': [],
                'agency': [],
                'kyc': [],
                'reporting': ['GET']
            }
        }
        
        view_name = view.__class__.__name__
        method = request.method
        
        # Vérifier les permissions pour chaque rôle
        for role in user_groups:
            if role in permission_map.get(view_name, {}):
                allowed_methods = permission_map[view_name][role]
                if method in allowed_methods:
                    return True
        
        return False
    
    def has_object_permission(self, request, view, obj):
        # Vérifier d'abord l'existence de l'utilisateur dans la DB
        bank_db = getattr(request, 'source_bank_db', 'default')
        
        try:
            from apps.users.models import User
            User.objects.using(bank_db).get(id=request.user.id)
        except User.DoesNotExist:
            return False
            
        return self.has_permission(request, view)