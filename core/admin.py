from django.contrib import admin
from .models import Vereador, Sessao, Pauta, Votacao, Relatorio, Cronometro
from .models import CamaraMunicipal
from .models import Live  

# Registrando os modelos para aparecerem no painel de administração
admin.site.register(Vereador)
admin.site.register(Sessao)
admin.site.register(Pauta)
admin.site.register(Votacao)
admin.site.register(Relatorio)
admin.site.register(Cronometro)
admin.site.register(CamaraMunicipal)

class LiveAdmin(admin.ModelAdmin):
    list_display = ('nome', 'link')  # Definindo quais campos serão mostrados no painel de administração
    search_fields = ('nome',)  # Adicionando a possibilidade de buscar pelo nome da live

admin.site.register(Live, LiveAdmin)



