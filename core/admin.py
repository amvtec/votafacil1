from django.contrib import admin
from .models import Vereador, Sessao, Pauta, Votacao, Relatorio, Cronometro
from .models import CamaraMunicipal

# Registrando os modelos para aparecerem no painel de administração
admin.site.register(Vereador)
admin.site.register(Sessao)
admin.site.register(Pauta)
admin.site.register(Votacao)
admin.site.register(Relatorio)
admin.site.register(Cronometro)
admin.site.register(CamaraMunicipal)



