from django.contrib import admin
from .models import AgencyAccount, BusinessAccount, PersonalAccount, InternAccount
# Register your models here.


admin.site.register(AgencyAccount)
admin.site.register(BusinessAccount)        
admin.site.register(PersonalAccount)
admin.site.register(InternAccount)