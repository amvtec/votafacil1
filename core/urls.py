from django.urls import path
from django.conf import settings
from .views import listar_relatorios, gerar_relatorio
from . import views
from . import views
from .views import listar_vereadores_view  # ✅ Adicione isso aqui
from .views import editar_sessao
from .views import editar_pauta
from django.conf.urls.static import static
from core.views import (
    login_view, logout_view, painel_presidente, painel_vereador, 
    registrar_presenca, votar_pauta, registrar_voto, abrir_sessao, 
    encerrar_sessao, iniciar_votacao, encerrar_votacao, voto_desempate, 
    ver_resultados, gerar_relatorio, painel_publico, ver_presencas, 
    pautas_presidente, visualizar_pautas, gerar_relatorio_presencas, 
    remover_pauta, api_vereadores_presencas, api_painel_publico, 
    api_pautas_do_dia, pautas_do_dia, reabrir_votacao, sessoes_encerradas, 
    reabrir_sessao
)

urlpatterns = [
    # Autenticação
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path('termos/', views.termos_de_uso, name='termos_de_uso'),
    path('cadastros/vereadores/', listar_vereadores_view, name='listar_vereadores'),

    
    # Painel do Vereador
    path("vereador/", painel_vereador, name="painel_vereador"),
    path("vereador/presenca/", registrar_presenca, name="registrar_presenca"),
    path("vereador/votar/<int:pauta_id>/", votar_pauta, name="votar_pauta"),
    path("vereador/registrar_voto/<int:pauta_id>/", registrar_voto, name="registrar_voto"),
    path("pautas/", visualizar_pautas, name="visualizar_pautas"),
    path('atualizar-botoes-voto/', views.atualizar_botoes_voto, name='atualizar_botoes_voto'),
    path('cronometro-publico/', views.cronometro_publico, name='cronometro_publico'),
    path('cronometro/iniciar/<int:vereador_id>/', views.iniciar_cronometro, name='iniciar_cronometro'),
    path('cronometro/pausar/<int:vereador_id>/', views.pausar_cronometro, name='pausar_cronometro'),
    path('cronometro/parar/<int:vereador_id>/', views.parar_cronometro, name='parar_cronometro'),
    path('cronometro/adicionar/<int:vereador_id>/', views.adicionar_tempo, name='adicionar_tempo'),
    path('painel-cronometro/', views.painel_cronometro, name='painel_cronometro'),
    path('api/cronometro/tempo/<int:vereador_id>/', views.tempo_restante, name='tempo_restante'),
    path('api/cronometro-ativo/', views.api_cronometro_ativo, name='api_cronometro_ativo'),

    
    # Painel do Presidente
    path("presidente/", painel_presidente, name="painel_presidente"),
    path("presidente/abrir_sessao/<int:sessao_id>/", abrir_sessao, name="abrir_sessao"),
    path("presidente/encerrar_sessao/<int:sessao_id>/", encerrar_sessao, name="encerrar_sessao"),
    path("presidente/iniciar_votacao/<int:pauta_id>/<str:tipo_votacao>/", iniciar_votacao, name="iniciar_votacao"),
    path("presidente/encerrar_votacao/", encerrar_votacao, name="encerrar_votacao"),
    path("presidente/voto_desempate/<int:pauta_id>/", voto_desempate, name="voto_desempate"),
    path("presidente/ver_resultados/", ver_resultados, name="ver_resultados"),
    path("presidente/ver-presencas/<int:sessao_id>/", ver_presencas, name="ver_presencas"),
    path("presidente/remover_pauta/<int:pauta_id>/", remover_pauta, name="remover_pauta"),
    path("presidente/reabrir_votacao/<int:pauta_id>/", reabrir_votacao, name="reabrir_votacao"),
    path("presidente/pautas/", pautas_presidente, name="pautas_presidente"),
    path('presidente/iniciar_votacao/<int:pauta_id>/<str:tipo_votacao>/<str:modalidade>/', iniciar_votacao, name='iniciar_votacao'),
    path('api/sessao-ativa/', views.api_sessao_ativa, name='api_sessao_ativa'),
    
    
    # Sessões
    path("sessoes-encerradas/", sessoes_encerradas, name="sessoes_encerradas"),
    path("reabrir-sessao/<int:sessao_id>/", reabrir_sessao, name="reabrir_sessao"),
    
    # Relatórios
    path("relatorio-presencas/<int:sessao_id>/", gerar_relatorio_presencas, name="gerar_relatorio_presencas"),
    path("presidente/gerar_relatorio/<int:sessao_id>/", gerar_relatorio, name="gerar_relatorio"),
    path('relatorios/', listar_relatorios, name='listar_relatorios'),
    path('relatorios/sessao/<int:sessao_id>/', gerar_relatorio, name='gerar_relatorio'),
    
    # Painel Público
    path("painel_publico/", painel_publico, name="painel_publico"),
    path("api/vereadores_presencas/", api_vereadores_presencas, name="api_vereadores_presencas"),
    path("api/painel-publico/", api_painel_publico, name="api_painel_publico"),
    path("api/pautas_do_dia/", api_pautas_do_dia, name="api_pautas_do_dia"),



    path('login/', views.login_usuario, name='login'),
    path('logout/', views.logout_usuario, name='logout'),
    path('painel-cadastros/', views.painel_cadastros, name='painel_cadastros'),
    
    path('cadastrar-sessao/', views.cadastrar_sessao, name='cadastrar_sessao'),
    path('cadastrar-pauta/', views.cadastrar_pauta, name='cadastrar_pauta'),
    path('cadastrar-vereador/', views.cadastrar_vereador, name='cadastrar_vereador'),
    path('cadastrar-camara/', views.cadastrar_camara, name='cadastrar_camara'),
    path('login-admin/', views.login_admin, name='login_admin'),
    path('listar-sessoes/', views.listar_sessoes, name='listar_sessoes'),
    path('listar-pautas/', views.listar_pautas, name='listar_pautas'),
    path('editar-vereador/<int:vereador_id>/', views.editar_vereador, name='editar_vereador'),
    path('dados-camara/', views.dados_camara, name='dados_camara'),
    path('editar-sessao/<int:sessao_id>/', editar_sessao, name='editar_sessao'),
    path('editar-pauta/<int:pauta_id>/', editar_pauta, name='editar_pauta'),


    
]

# 🔹 Configuração para servir arquivos de mídia (PDFs das pautas)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
