
from django.http import JsonResponse
from apps.banks.models import Bank

class BankMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        
        if request.path.startswith('/admin/'):
            return self.get_response(request)
        
        source_bank_code = request.headers.get('X-Source-Bank-Code')
        destination_bank_code = request.headers.get('X-Destination-Bank-Code')

        if source_bank_code and destination_bank_code:
            try:
                source_bank = Bank.objects.get(code=source_bank_code)
                destination_bank = Bank.objects.get(code=destination_bank_code)
                request.source_bank = source_bank
                request.source_bank_db = source_bank.code
                request.destination_bank = destination_bank
                request.destination_bank_db = destination_bank.code
            except Bank.DoesNotExist:
                return JsonResponse(
                    {"error": "Une des banques n'a pas été trouvée pour les codes fournis."},
                    status=400
                )
        else:
            return JsonResponse(
                {"error": "Les codes bancaires source et destination sont requis."},
                status=400
            )

        response = self.get_response(request)
        return response