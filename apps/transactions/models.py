from django.db import models
from apps.accounts.models import Account
from django.utils import timezone
import uuid
import random



class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('transfer', 'Transfer'),
        ('withdrawal', 'Withdrawal'),
        ('deposit', 'Deposit'),
        ('paiement', 'Paiement'),
    ]

    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failure', 'Failure'),
        ('pending', 'Pending'),
    ]

    id = models.CharField(
        primary_key=True,
        max_length=20,  
        unique=True,
        editable=False
    )
    type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    external_account_number = models.CharField(max_length=50, null=True, blank=True)
    external_bank = models.CharField(max_length=50, null=True, blank=True)
    source_account = models.ForeignKey(
        Account, related_name='source_transactions', null=True, blank=True, on_delete=models.CASCADE
    )
    destination_account = models.ForeignKey(
        Account, related_name='destination_transactions', null=True, blank=True, on_delete=models.CASCADE
    )

    # def save(self, *args, **kwargs):
    #     if not self.id:
    #         self.id = f"TR{uuid.uuid4().int % 10**9:09d}"  
    #     super().save(*args, **kwargs)
    def save(self, *args, **kwargs):
        if not self.id:
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')  
            random_number = f"{uuid.uuid4().int % 1000:03d}"  
            self.id = f"TR{timestamp}{random_number}" 
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.id} - {self.type} - {self.amount} - {self.date} - {self.status}"

class PreTransaction(models.Model):
    id = models.CharField(
        primary_key=True,
        max_length=20,
        unique=True,
        editable=False
    )
    code = models.CharField(max_length=4, unique=True)
    client_phone = models.CharField(max_length=15)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def generate_unique_code(self, db_to_use=None):
      
        while True:
            code = f"{random.randint(1000, 9999)}"
            if not PreTransaction.objects.using(db_to_use).filter(code=code).exists():
                return code
    
    def save(self, *args, **kwargs):
        db_to_use = kwargs.get('using', None)
        
        if not self.id:
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            random_number = f"{uuid.uuid4().int % 1000:03d}"
            self.id = f"PT{timestamp}{random_number}"
        
        if not self.code:
            self.code = self.generate_unique_code(db_to_use=db_to_use)
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.id} - Code: {self.code} - {self.client_phone} - {self.amount}"
    
class FeeRule(models.Model):
    transaction_type = models.CharField(
        max_length=50,
        choices=[('transfer', 'Transfer'), ('withdrawal', 'Withdrawal'),
                  ('deposit', 'Deposit'), ('paiement', 'Paiement')]
    )
    max_amount = models.DecimalField(max_digits=20, decimal_places=2)
    fee_amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ['max_amount']

    def __str__(self):
        return f"{self.transaction_type} <= {self.max_amount} : {self.fee_amount}"    

class PaymentRequest(models.Model):
    merchant = models.ForeignKey(Account, on_delete=models.CASCADE, limit_choices_to={'type_account': 'business'})
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    status = models.CharField(max_length=20, choices=[('pending', 'En attente'), ('paid', 'Payé')], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Paiement {self.code} - {self.amount} MRO - {self.status}"

    
class Fee(models.Model):
    transaction = models.OneToOneField('Transaction', on_delete=models.CASCADE, related_name='fee')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Fee of {self.amount} for Transaction {self.transaction.id}"    