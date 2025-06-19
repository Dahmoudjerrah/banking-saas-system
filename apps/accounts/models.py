
from django.db import models
from apps.users.models import User
import random
from django.core.validators import MinValueValidator, MaxValueValidator

class AccountManager(models.Manager):
    def get_account(self, account_id, using=None):
        return self.using(using).get(id=account_id)
    
    def generate_unique_code(self, bank_db=None):
        while True:
            code = str(random.randint(100000, 999999))
            if not self.db_manager(bank_db).filter(code=code).exists():
                return code
            
class AbstractAccount(models.Model):
    STATUS_CHOICES = (
        ('ACTIVE', 'Actif'),
        ('PENDING', 'En attente'),
        ('BLOCKED', 'Bloqué'),
        ('CLOSED', 'Fermé'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)  
    account_number = models.CharField(max_length=30, unique=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True)
    

 
    objects = AccountManager()

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.type_account} - {self.account_number} - {self.status}"  
      
    @staticmethod
    def generate_account_number():
        code_pays = "MR"
        cle_controle = f"{random.randint(10, 99)}"  
        code_banque = "00020"  
        code_guichet = "00101"  
        numero_compte = str(random.randint(10**10, 10**11 - 1))  
        cle_rib = f"{random.randint(10, 99)}"  
        return f"{code_pays}{cle_controle}{code_banque}{code_guichet}{numero_compte}{cle_rib}"
    
    

class PersonalAccount(AbstractAccount):
    class Meta:
        app_label = 'accounts'


class BusinessAccount(AbstractAccount):
    registration_number = models.CharField(max_length=50, null=True, blank=True)
    tax_id = models.CharField(max_length=50, null=True, blank=True)
    code = models.CharField(max_length=6, null=True, blank=True, unique=True)

    class Meta:
        app_label = 'accounts'

class AgencyAccount(AbstractAccount):
    registration_number = models.CharField(max_length=50, null=True, blank=True)
    tax_id = models.CharField(max_length=50, null=True, blank=True)
    code = models.CharField(max_length=6, null=True, blank=True, unique=True)
    deposit_porcentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    retrai_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        app_label = 'accounts'

class InternAccount(AbstractAccount):
    PURPOSE_CHOICES = [
        ('commission', 'Commission'),
        ('frais', 'Frais'),
        ('taxe', 'Taxe'),
        ('reserve', 'Reserve'),
    ]

    purpose = models.CharField(max_length=50, choices=PURPOSE_CHOICES, null=True, blank=True)

    class Meta:
        app_label = 'accounts'