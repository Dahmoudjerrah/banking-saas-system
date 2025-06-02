from django.db import models
class AdminBankSelector(models.Model):
    code = models.CharField(max_length=100, blank=True)

    class Meta:
        managed = False  
        verbose_name = "Sélectionner la banque courante"
        verbose_name_plural = "Sélectionner la banque courante"  
