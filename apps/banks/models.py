from django.db import models


from django.db import models

class Bank(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    
    def __str__(self):
        return self.name

class BankFeature(models.Model):
    bank = models.ForeignKey(Bank, on_delete=models.CASCADE, related_name='features')
    feature_name = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ('bank', 'feature_name')
    
    def __str__(self):
        return f"{self.bank.name} - {self.feature_name}"