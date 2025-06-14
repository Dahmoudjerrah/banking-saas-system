from django.db import models
from apps.accounts.models import Account
from django.utils import timezone
import uuid
import random

from datetime import timedelta
import secrets
import string


class PasswordResetOTP(models.Model):
    phone_number = models.CharField(max_length=20)
    otp_code = models.CharField(max_length=6)
    reset_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    attempts = models.IntegerField(default=0)

    class Meta:
        db_table = 'password_reset_otp'
        indexes = [
            models.Index(fields=['phone_number']),
            models.Index(fields=['otp_code']),
            models.Index(fields=['reset_token']),
            models.Index(fields=['created_at']),
        ]

    def save(self, *args, **kwargs):
        if not self.expires_at:
            # OTP expire dans 10 minutes
            self.expires_at = timezone.now() + timedelta(minutes=10)
        if not self.reset_token and self.is_verified:
            # Générer un token de réinitialisation unique
            self.reset_token = self.generate_reset_token()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_reset_token():
        """Génère un token de réinitialisation sécurisé"""
        return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(64))

    def is_expired(self):
        """Vérifie si l'OTP a expiré"""
        return timezone.now() > self.expires_at

    def is_valid_for_reset(self):
        """Vérifie si le token est valide pour la réinitialisation"""
        return (
            self.is_verified and 
            not self.is_used and 
            not self.is_expired() and 
            self.reset_token is not None
        )

    def mark_as_used(self, using=None):
        """
        Marque le token comme utilisé
        CORRECTION: Accepter le paramètre using pour multi-DB
        """
        self.is_used = True
        self.save(using=using)  

    def __str__(self):
        return f"Password Reset OTP for {self.phone_number} - {'Verified' if self.is_verified else 'Pending'}"


#////////////////////////////////////////////
class OTPVerification(models.Model):
    phone_number = models.CharField(max_length=8)
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)
    attempts = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'otp_verification'
        indexes = [
            models.Index(fields=['phone_number', 'created_at']),
        ]
    
    def is_expired(self):
        """Vérifie si l'OTP a expiré (1 minute)"""
        expiry_time = self.created_at + timedelta(minutes=1)
        return timezone.now() > expiry_time
    
    def is_valid(self):
        """Vérifie si l'OTP est encore valide"""
        return not self.is_expired() and not self.is_verified and self.attempts < 3
    
    @classmethod
    def generate_otp(cls):
        """Génère un code OTP de 6 chiffres"""
        return ''.join(random.choices(string.digits, k=6))
    
    @classmethod
    def cleanup_expired(cls, db_alias='default'):
        """Supprime les OTP expirés"""
        expiry_time = timezone.now() - timedelta(minutes=1)
        cls.objects.using(db_alias).filter(created_at__lt=expiry_time).delete()
    
    def save(self, *args, **kwargs):
        
        if not self.pk:
            db_alias = kwargs.get('using', 'default')
            self.__class__.cleanup_expired(db_alias)
        super().save(*args, **kwargs)

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
    is_used = models.BooleanField(default=False)

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
    
    def is_active(self):
        
        if self.is_used:
            return False
        expiration_time = self.created_at + timezone.timedelta(minutes=5)
        return timezone.now() <= expiration_time
    
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