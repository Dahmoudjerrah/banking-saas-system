from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import AbstractUser,BaseUserManager




class CustomUserManager(BaseUserManager):
    def create_user(self, email, phone_number, password=None, **extra_fields):
        if not email:
            raise ValueError("L'utilisateur doit avoir une adresse email")
        email = self.normalize_email(email)
        user = self.model(email=email, phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, phone_number, password,username=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        return self.create_user(email, phone_number, password, **extra_fields)
class User(AbstractUser):
    phone_number = models.CharField(max_length=15, blank=True, null=True,unique=True)
    date_of_birth = models.DateField(null=True, blank=True)
  
    objects = CustomUserManager()
    USERNAME_FIELD = 'phone_number'
    def __str__(self):
        return self.username