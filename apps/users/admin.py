from django.contrib import admin
from .models import User

class UserAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        selected_db = request.session.get('admin_selected_bank', 'default')
        return super().get_queryset(request).using(selected_db)
admin.site.register(User, UserAdmin)    
