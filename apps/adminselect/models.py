from django.db import models
from django.contrib.auth.models import  Group

from apps.users.models import User

class AdminBankSelector(models.Model):
    code = models.CharField(max_length=100, blank=True)

    class Meta:
        managed = False  
        verbose_name = "Sélectionner la banque courante"
        verbose_name_plural = "Sélectionner la banque courante"  


class GroupApiPermission(models.Model):
    """
    Permissions API pour les groupes
    """
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='api_permissions')
    view_name = models.CharField(max_length=100, help_text="Nom de la vue API (ex: TransactionHistoryView)")
    is_active = models.BooleanField(default=True, help_text="Activer/désactiver cette permission")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Permission API Groupe"
        verbose_name_plural = "Permissions API Groupe"
        unique_together = ['group', 'view_name']
    
    def __str__(self):
        return f"{self.group.name} → {self.view_name}"

class UserApiPermission(models.Model):
    """
    Permissions API pour les utilisateurs (y compris admin avec restrictions)
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_permissions')
    view_name = models.CharField(max_length=100, help_text="Nom de la vue API")
    is_active = models.BooleanField(default=True, help_text="Activer/désactiver cette permission")
    granted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='granted_permissions')
    granted_at = models.DateTimeField(auto_now_add=True)
    is_admin_override = models.BooleanField(default=False, help_text="Permission spécifique pour admin (override l'accès complet)")
    
    class Meta:
        verbose_name = "Permission API Utilisateur"
        verbose_name_plural = "Permissions API Utilisateur"
        unique_together = ['user', 'view_name']
    
    def __str__(self):
        admin_tag = " [ADMIN OVERRIDE]" if self.is_admin_override else ""
        return f"{self.user.username} → {self.view_name}{admin_tag}"