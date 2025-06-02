from django.contrib import admin
from django import forms
from django.http import HttpResponseRedirect
from apps.banks.models import Bank
from django.utils.html import format_html
from .models import  AdminBankSelector
from django.middleware.csrf import get_token
from django.utils.safestring import mark_safe

class AdminBankSelectorAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        
        return self.model.objects.none()

    def changelist_view(self, request, extra_context=None):
        if request.method == "POST":
            selected_code = request.POST.get('code')
            if selected_code:
                request.session['admin_selected_bank'] = selected_code
                self.message_user(request, f"Banque sélectionnée : {selected_code}")
                return HttpResponseRedirect(request.path)

        csrf_token = get_token(request)

        bank_options = "".join(
            f'<option value="{b.code}">{b.name}</option>' for b in Bank.objects.all()
        )

        form_html = format_html("""
            <form method="post" style="margin-top:1em;">
                <input type="hidden" name="csrfmiddlewaretoken" value="{}">
                <label for="id_code"><strong>Choisir une banque :</strong></label>
                <select name="code" id="id_code">{}</select>
                <input type="submit" value="Valider" class="default">
            </form>
        """, csrf_token, mark_safe(bank_options))

        self.message_user(request, form_html, level='INFO')
        return super().changelist_view(request, extra_context)


admin.site.register(AdminBankSelector, AdminBankSelectorAdmin)