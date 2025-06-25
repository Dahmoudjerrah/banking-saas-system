from rest_framework import permissions
from django.contrib.auth.models import Group
from .models import GroupApiPermission, UserApiPermission

class ApiAccessPermission(permissions.BasePermission):
    """
    Permission avec gestion spéciale pour admin :
    - Admin a accès complet par défaut
    - SAUF si des permissions spécifiques sont définies pour cet admin
    - Les autres utilisateurs suivent le système groupe + permissions individuelles
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Récupérer la base de données utilisée
        bank_db = getattr(request, 'source_bank_db', 'default')
        
        # Vérifier que l'utilisateur existe dans cette base de données
        try:
            from apps.users.models import User
            db_user = User.objects.using(bank_db).get(id=request.user.id)
        except User.DoesNotExist:
            return False
        
        view_name = view.__class__.__name__
        
        # Gestion spéciale pour les admins
        if self._is_admin_user(db_user, bank_db):
            return self._check_admin_access(db_user, view_name, bank_db)
        
        # Pour les autres utilisateurs : vérification normale
        # 1. Vérifier l'accès via groupe
        if self._check_group_permissions(db_user, view_name, bank_db):
            return True
        
        # 2. Vérifier l'accès via permissions individuelles
        if self._check_user_permissions(db_user, view_name, bank_db):
            return True
            
        return False
    
    def _is_admin_user(self, user, bank_db):
        """
        Vérifier si l'utilisateur est admin
        """
        user_groups = user.groups.using(bank_db).values_list('name', flat=True)
        return 'admin' in user_groups
    
    def _check_admin_access(self, user, view_name, bank_db):
        """
        Gestion spéciale pour les admins :
        - Si des permissions spécifiques existent pour cet admin → utiliser ces permissions
        - Sinon → accès complet
        """
        # Vérifier s'il y a des permissions spécifiques définies pour cet admin
        admin_specific_permissions = UserApiPermission.objects.using(bank_db).filter(
            user=user,
            is_admin_override=True,
            is_active=True
        )
        
        if admin_specific_permissions.exists():
            # L'admin a des restrictions spécifiques
            return admin_specific_permissions.filter(view_name=view_name).exists()
        else:
            # Pas de restrictions spécifiques → accès complet
            return True
    
    def _check_group_permissions(self, user, view_name, bank_db):
        """
        Vérifier l'accès via les permissions du groupe
        """
        user_groups = user.groups.using(bank_db).all()
        
        if not user_groups.exists():
            return False
        
        for group in user_groups:
            if GroupApiPermission.objects.using(bank_db).filter(
                group=group,
                view_name=view_name,
                is_active=True
            ).exists():
                return True
        
        return False
    
    def _check_user_permissions(self, user, view_name, bank_db):
        """
        Vérifier l'accès via permissions individuelles (non-admin)
        """
        return UserApiPermission.objects.using(bank_db).filter(
            user=user,
            view_name=view_name,
            is_active=True,
            is_admin_override=False  # Permissions normales seulement
        ).exists()
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)