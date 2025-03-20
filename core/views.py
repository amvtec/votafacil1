# views.py - Desenvolvimento dos Painéis do Vereador e Presidente

from django.shortcuts import render, redirect, get_object_or_404
from django.utils.timezone import now
from .models import Sessao, Vereador, Pauta, Votacao, Cronometro, Relatorio
from django.http import HttpResponse
from django.template.loader import render_to_string
import tempfile
import os
from django.conf import settings
from .forms import PautaForm
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from django.http import JsonResponse
from reportlab.platypus import Spacer
from .models import PresencaRegistrada
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync




def login_view(request):
    if request.method == "POST":
        cpf = request.POST.get("cpf")
        senha = request.POST.get("senha")

        print(f"Tentativa de login com CPF: {cpf} e Senha: {senha}")  # Log para debug

        try:
            vereador = Vereador.objects.get(cpf=cpf)
            print(f"Vereador encontrado: {vereador.nome}")
        except Vereador.DoesNotExist:
            print("Erro: Vereador não encontrado.")
            vereador = None

        if vereador and vereador.senha == senha:
            print("Login bem-sucedido! Redirecionando...")
            request.session["vereador_id"] = vereador.id
            if vereador.funcao == "Presidente":
                return redirect("painel_presidente")
            else:
                return redirect("painel_vereador")
        else:
            print("Erro: CPF ou senha incorretos.")
            return render(request, "core/login.html", {"erro": "CPF ou senha incorretos"})

    return render(request, "core/login.html")


def logout_view(request):
    request.session.flush()  # Remove os dados da sessão
    return redirect("login")

def painel_vereador(request):
    vereador_id = request.session.get("vereador_id")
    if not vereador_id:
        return redirect("login")

    vereador = get_object_or_404(Vereador, id=vereador_id)

    # 🔹 **Apenas sessões em andamento ficam visíveis para os vereadores**
    sessao_ativa = Sessao.objects.filter(status="Em Andamento").first()

    pautas = Pauta.objects.filter(sessao=sessao_ativa, status="Em Votação") if sessao_ativa else []

    votos_realizados = Votacao.objects.filter(vereador=vereador, pauta__in=pautas).values_list("pauta_id", flat=True)

    return render(request, "core/painel_vereador.html", {
        "vereador": vereador,
        "pautas": pautas,
        "sessao_ativa": sessao_ativa,
        "votos_realizados": votos_realizados,
    })




def painel_presidente(request):
    vereador_id = request.session.get("vereador_id")
    if not vereador_id:
        return redirect("login")

    presidente = get_object_or_404(Vereador, id=vereador_id, funcao='Presidente')

    # 🔹 **Filtra apenas sessões que NÃO estão arquivadas**
    sessoes_ativas = Sessao.objects.exclude(status='Arquivada')

    return render(request, 'core/painel_presidente.html', {
        'presidente': presidente,
        'sessoes': sessoes_ativas,  # Apenas sessões ativas
    })




def registrar_presenca(request):
    vereador_id = request.session.get("vereador_id")
    if not vereador_id:
        messages.error(request, "Você precisa estar logado para registrar presença.")
        return redirect("login")
    
    vereador = get_object_or_404(Vereador, id=vereador_id)
    sessao = Sessao.objects.filter(status='Em Andamento').first()

    if not sessao:
        messages.warning(request, "Nenhuma sessão está em andamento.")
        return redirect("painel_vereador")

    # Salvar presença
    _, created = Votacao.objects.update_or_create(
        vereador=vereador, pauta=None, defaults={'presenca': True}
    )

    if created:
        messages.success(request, "Presença registrada com sucesso! ✅")
    else:
        messages.info(request, "Você já registrou sua presença.")

    return redirect("painel_vereador")



def registrar_voto(request, pauta_id):
    vereador_id = request.session.get("vereador_id")
    if not vereador_id:
        messages.error(request, "Você precisa estar logado para votar.")
        return redirect("login")
    
    vereador = get_object_or_404(Vereador, id=vereador_id)
    pauta = get_object_or_404(Pauta, id=pauta_id)

    if request.method == "POST":
        voto = request.POST.get("voto")
        Votacao.objects.update_or_create(vereador=vereador, pauta=pauta, defaults={"voto": voto})
        messages.success(request, "Voto registrado com sucesso! 🗳️")

        return redirect("painel_vereador")

    return render(request, "votacao.html", {"pauta": pauta})




from django.db.models import Count

def encerrar_votacao(request):
    vereador_id = request.session.get("vereador_id")
    if not vereador_id:
        messages.error(request, "⚠️ Você precisa estar logado para realizar esta ação.")
        return redirect("login")

    # 🔹 Verifica se o usuário logado é o presidente
    presidente = get_object_or_404(Vereador, id=vereador_id, funcao="Presidente")

    # 🔹 Verifica se há uma sessão ativa
    sessao = Sessao.objects.filter(status="Em Andamento").first()
    if not sessao:
        messages.warning(request, "⚠️ Nenhuma sessão está ativa no momento.")
        return redirect("painel_presidente")

    # 🔹 Verifica se há pautas em votação
    pautas_em_votacao = Pauta.objects.filter(sessao=sessao, status="Em Votação")
    if not pautas_em_votacao.exists():
        messages.info(request, "ℹ️ Nenhuma pauta está em votação para ser encerrada.")
        return redirect("painel_presidente")

    # 🔹 Atualiza cada pauta com base nos votos
    for pauta in pautas_em_votacao:
        votos = Votacao.objects.filter(pauta=pauta).values("voto").annotate(total=Count("voto"))
        
        votos_sim = next((item["total"] for item in votos if item["voto"] == "Sim"), 0)
        votos_nao = next((item["total"] for item in votos if item["voto"] == "Não"), 0)
        votos_abstencao = next((item["total"] for item in votos if item["voto"] == "Abstenção"), 0)

        total_votantes = votos_sim + votos_nao + votos_abstencao
        vereadores_presentes = Votacao.objects.filter(pauta=None, presenca=True).count()

        # 🔹 Define o critério de aprovação com base no tipo da votação
        if pauta.tipo_votacao == "Comum":
            maioria = (vereadores_presentes // 2) + 1  # Maioria simples
        else:
            maioria = (2 * vereadores_presentes) // 3  # Maioria qualificada (2/3)

        # 🔹 Determina o resultado da votação
        if votos_sim >= maioria:
            pauta.status = "Aprovada"
        elif votos_nao >= maioria:
            pauta.status = "Rejeitada"
        else:
            pauta.status = "Encerrada"

        pauta.save()

    messages.success(request, "✅ Todas as pautas foram encerradas e o status foi atualizado!")
    return redirect("painel_presidente")


def voto_desempate(request, pauta_id):
    vereador_id = request.session.get("vereador_id")
    if not vereador_id:
        return redirect("login")
    
    presidente = get_object_or_404(Vereador, id=vereador_id, funcao='Presidente')
    pauta = get_object_or_404(Pauta, id=pauta_id)

    if request.method == "POST":
        voto = request.POST.get("voto")
        Votacao.objects.create(vereador=presidente, pauta=pauta, voto=voto)
        return redirect("painel_presidente")

    return render(request, "voto_desempate.html", {"pauta": pauta})

def painel_publico(request):
    sessao = Sessao.objects.filter(status='Em Andamento').first()
    if not sessao:
        return render(request, "painel_publico.html", {"mensagem": "Nenhuma sessão ativa no momento."})

    pautas = Pauta.objects.filter(sessao=sessao)
    votos = []

    for pauta in pautas:
        resultado = {
            "pauta": pauta,
            "sim": Votacao.objects.filter(pauta=pauta, voto="Sim").count(),
            "nao": Votacao.objects.filter(pauta=pauta, voto="Não").count(),
            "abstencao": Votacao.objects.filter(pauta=pauta, voto="Abstenção").count(),
        }
        votos.append(resultado)

    return render(request, "painel_publico.html", {"sessao": sessao, "votos": votos})

def votar_pauta(request, pauta_id):
    vereador_id = request.session.get("vereador_id")
    if not vereador_id:
        return redirect("login")

    vereador = get_object_or_404(Vereador, id=vereador_id)
    pauta = get_object_or_404(Pauta, id=pauta_id)

    if request.method == "POST":
        voto = request.POST.get("voto")  # 'Sim', 'Não', 'Abstenção'
        Votacao.objects.update_or_create(vereador=vereador, pauta=pauta, defaults={"voto": voto})
        return redirect("painel_vereador")

    return render(request, "votacao.html", {"pauta": pauta})

def abrir_sessao(request, sessao_id):
    vereador_id = request.session.get("vereador_id")
    if not vereador_id:
        return redirect("login")

    presidente = get_object_or_404(Vereador, id=vereador_id, funcao="Presidente")
    sessao = get_object_or_404(Sessao, id=sessao_id)

    if sessao.status != "Em Andamento":
        sessao.status = "Em Andamento"
        sessao.save()

    return redirect("painel_presidente")

def encerrar_sessao(request, sessao_id):
    """ Arquiva a sessão e salva as presenças antes de resetar os dados. """
    sessao = get_object_or_404(Sessao, id=sessao_id)

    if sessao.status == "Em Andamento":
        # 🔹 1️⃣ Salvar as presenças antes de encerrar a sessão
        vereadores_presentes = Votacao.objects.filter(pauta=None, presenca=True).values_list("vereador", flat=True)
        for vereador_id in vereadores_presentes:
            PresencaRegistrada.objects.create(sessao=sessao, vereador_id=vereador_id)

        # 🔹 2️⃣ Arquivar a sessão
        sessao.status = "Arquivada"
        sessao.save()

        # 🔹 3️⃣ Zerar as presenças para uma futura sessão
        Votacao.objects.filter(pauta=None).delete()  # Remove os registros de presença

        messages.success(request, f"📌 Sessão {sessao.nome} foi arquivada! Presenças salvas.")

        # 🔹 4️⃣ (Opcional) Notificar o painel público via WebSockets:
        #     Se você configurou Django Channels e um Consumer "PainelPublicoConsumer"
        #     e todos os navegadores estiverem em um group chamado 'painelPublicoGroup',
        #     então envie esse "sessao_encerrada" para derrubar o painel em tempo real.
        channel_layer = get_channel_layer()
        if channel_layer is not None:
            async_to_sync(channel_layer.group_send)(
                'painelPublicoGroup',
                {'type': 'sessao_encerrada'}
            )

    return redirect("painel_presidente")

def iniciar_votacao(request, pauta_id, tipo_votacao):
    pauta = get_object_or_404(Pauta, id=pauta_id)

    # 🔹 Ajuste para garantir que o tipo seja armazenado corretamente
    if tipo_votacao == "aberta":
        pauta.votacao_aberta = True
    elif tipo_votacao == "fechada":
        pauta.votacao_aberta = False

    pauta.status = "Em Votação"  # Atualiza o status
    pauta.save(update_fields=['votacao_aberta', 'status'])  # 🔹 SALVA APENAS OS CAMPOS ALTERADOS

    messages.success(request, f'Votação iniciada como {tipo_votacao.upper()}!')
    return redirect("painel_presidente")



def ver_resultados(request):
    """ Exibe os resultados das votações das pautas da sessão ativa """
    vereador_id = request.session.get("vereador_id")
    if not vereador_id:
        return redirect("login")

    sessao = Sessao.objects.filter(status='Em Andamento').first()
    if not sessao:
        return redirect("painel_presidente")  # Redireciona caso não haja sessão ativa

    pautas = Pauta.objects.filter(sessao=sessao)
    resultados = []

    for pauta in pautas:
        votos = Votacao.objects.filter(pauta=pauta)
        contagem_votos = {
            "Sim": votos.filter(voto="Sim").count(),
            "Não": votos.filter(voto="Não").count(),
            "Abstenção": votos.filter(voto="Abstenção").count(),
        }
        resultados.append({"pauta": pauta, "votos": contagem_votos})

    return render(request, "ver_resultados.html", {"resultados": resultados})



# Função para formatar texto dentro das tabelas
def format_text(text):
    """ Formatação padrão para células da tabela """
    table_text_style = ParagraphStyle(
        "TableText",
        fontSize=10,
        leading=12,
        wordWrap='CJK',
    )
    return Paragraph(text, table_text_style) if text else "-"

def gerar_relatorio(request, sessao_id):
    # Obtém a sessão e suas pautas
    sessao = Sessao.objects.get(id=sessao_id)
    pautas = Pauta.objects.filter(sessao=sessao)
    votos = Votacao.objects.filter(pauta__in=pautas)

    # Configura a resposta HTTP para PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="relatorio_sessao_{sessao.id}.pdf"'

    # Criar o documento PDF
    doc = SimpleDocTemplate(response, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    # 🔹 Estilos personalizados
    left_aligned_style = ParagraphStyle(name="LeftAligned", parent=styles["Normal"], alignment=0)
    centered_style = ParagraphStyle(name="Centered", parent=styles["Normal"], alignment=1)

    # 🔹 Cabeçalho com Logo e Informações da Câmara
    câmara_nome = "Câmara Municipal de Wanderlândia"
    câmara_endereco = "Av. Gomes Ferreira, 564 - Centro, Wanderlândia/TO"
    câmara_cnpj = "CNPJ: 00.237.271/0001-65"
    logo_path = "static/img/logo.png"

    try:
        img = Image(logo_path, width=80, height=80)
        elements.append(img)
    except Exception:
        elements.append(Paragraph("LOGO NÃO DISPONÍVEL", left_aligned_style))

    elements.append(Paragraph(f"<b>{câmara_nome}</b>", left_aligned_style))
    elements.append(Paragraph(f"{câmara_endereco}", left_aligned_style))
    elements.append(Paragraph(f"{câmara_cnpj}", left_aligned_style))
    elements.append(Spacer(1, 10))  

    # 🔹 Informações da Sessão
    elements.append(Paragraph(f"<b>Relatório da Sessão:</b> {sessao.nome}", left_aligned_style))
    elements.append(Paragraph(f"Data: {sessao.data.strftime('%d/%m/%Y')}", left_aligned_style))
    elements.append(Paragraph(f"Horário: {sessao.hora.strftime('%H:%M')}", left_aligned_style))
    elements.append(Paragraph(f"Status: {sessao.status}", left_aligned_style))
    elements.append(Spacer(1, 15))

    # 🔹 Exibir cada pauta separadamente com seus votos
    for pauta in pautas:
        elements.append(Paragraph(f"<b>Pauta:</b> {pauta.titulo}", left_aligned_style))
        elements.append(Paragraph(f"<b>Tipo:</b> {pauta.tipo}", left_aligned_style))
        elements.append(Paragraph(f"<b>Autor:</b> {pauta.autor.nome}", left_aligned_style))
        elements.append(Paragraph(f"<b>Status:</b> {pauta.status}", left_aligned_style))

        # 🔹 Adicionar o Tipo de Votação (Simples, Absoluta, Qualificada)
        tipo_votacao_texto = "Não Definido"
        if pauta.tipo_votacao == "simples":
            tipo_votacao_texto = "Maioria Simples"
        elif pauta.tipo_votacao == "absoluta":
            tipo_votacao_texto = "Maioria Absoluta"
        elif pauta.tipo_votacao == "qualificada":
            tipo_votacao_texto = "Maioria Qualificada (2/3)"
        
        elements.append(Paragraph(f"<b>Tipo de Votação:</b> {tipo_votacao_texto}", left_aligned_style))
        elements.append(Paragraph(f"<b>Votação:</b> {'Aberta' if pauta.votacao_aberta else 'Secreta'}", left_aligned_style))
        elements.append(Spacer(1, 10))

        # 🔹 Contabilizando votos
        votos_da_pauta = votos.filter(pauta=pauta)
        votos_sim = votos_da_pauta.filter(voto="Sim").count()
        votos_nao = votos_da_pauta.filter(voto="Não").count()
        votos_abstencao = votos_da_pauta.filter(voto="Abstenção").count()

        # 🔹 Exibir os votos de acordo com o tipo de votação
        if pauta.votacao_aberta:
            if votos_da_pauta.exists():
                voto_data = [["Vereador", "Voto"]]
                for voto in votos_da_pauta:
                    voto_data.append([voto.vereador.nome, voto.voto])

                voto_col_widths = [3 * inch, 2 * inch]
                tabela_votos = Table(voto_data, colWidths=voto_col_widths)
                tabela_votos.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                elements.append(tabela_votos)
            else:
                elements.append(Paragraph("Nenhum voto registrado para esta pauta.", left_aligned_style))
        
        else:
            # 🔹 Em votação SECRETA, exibir apenas os totais
            elements.append(Paragraph("Votação secreta - Nomes ocultados", left_aligned_style))

        # 🔹 Exibir totais de votos (CENTRALIZADO)
        elements.append(Spacer(1, 10))
        totais_votos_texto = f"<b>Totais de Votos:</b> Sim: {votos_sim} | Não: {votos_nao} | Abstenção: {votos_abstencao}"
        elements.append(Paragraph(totais_votos_texto, centered_style))

        elements.append(Spacer(1, 20))  # Espaço entre pautas

    # Gera o PDF
    doc.build(elements)
    return response





def ver_presencas(request, sessao_id):
    sessao = get_object_or_404(Sessao, id=sessao_id)
    
    # 🔹 **Filtra os vereadores presentes na sessão selecionada**
    vereadores = Vereador.objects.all()
    for vereador in vereadores:
        vereador.presente = Votacao.objects.filter(
            vereador=vereador, sessao=sessao, presenca=True
        ).exists()

    return render(request, "core/ver_presencas.html", {
        "sessao": sessao,
        "vereadores": vereadores
    })




def editar_pauta(request, pauta_id):
    pauta = get_object_or_404(Pauta, id=pauta_id)
    
    if request.method == "POST":
        form = PautaForm(request.POST, instance=pauta)
        if form.is_valid():
            form.save()
            return redirect("painel_presidente")  # Redireciona após salvar
    else:
        form = PautaForm(instance=pauta)
    
    return render(request, "editar_pauta.html", {"form": form, "pauta": pauta})

def editar_pauta(request, pauta_id):
    pauta = get_object_or_404(Pauta, id=pauta_id)

    if request.method == "POST":
        form = PautaForm(request.POST, instance=pauta)
        if form.is_valid():
            form.save()
            return redirect("painel_presidente")  # Ou outra URL de retorno
    else:
        form = PautaForm(instance=pauta)

    return render(request, "editar_pauta.html", {"form": form, "pauta": pauta})

def remover_pauta(request, pauta_id):
    pauta = get_object_or_404(Pauta, id=pauta_id)
    pauta.delete()
    return redirect("painel_presidente")  # Redireciona para o painel do presidente

def reabrir_votacao(request, pauta_id):
    vereador_id = request.session.get("vereador_id")
    if not vereador_id:
        return redirect("login")

    presidente = get_object_or_404(Vereador, id=vereador_id, funcao="Presidente")
    pauta = get_object_or_404(Pauta, id=pauta_id)

    pauta.status = "Em Votação"  # Ou outro status que você usa
    pauta.save()

    return redirect("painel_presidente")

def pautas_presidente(request):
    vereador_id = request.session.get("vereador_id")
    if not vereador_id:
        return redirect("login")

    presidente = get_object_or_404(Vereador, id=vereador_id, funcao="Presidente")

    # Filtra apenas as pautas de sessões ativas (em andamento)
    sessao_ativa = Sessao.objects.filter(status="Em Andamento").first()

    if sessao_ativa:
        pautas = Pauta.objects.filter(sessao=sessao_ativa)
    else:
        pautas = []  # Nenhuma pauta deve aparecer se a sessão estiver encerrada

    return render(request, 'core/pautas_presidente.html', {'presidente': presidente, 'pautas': pautas, 'sessao_ativa': sessao_ativa})


from django.http import JsonResponse
from .models import Sessao, Pauta, Vereador, Votacao

from django.http import JsonResponse
from .models import Sessao, Pauta, Vereador, Votacao

from django.http import JsonResponse
from core.models import Sessao, Pauta, Vereador, Votacao

def listar_vereadores(pauta=None):
    vereadores = Vereador.objects.all()
    vereadores_data = []

    for vereador in vereadores:
        voto = "Nenhum"

        if pauta:
            voto_obj = Votacao.objects.filter(vereador=vereador, pauta=pauta).first()
            if voto_obj:
                voto = voto_obj.voto

        vereadores_data.append({
            "id": vereador.id,
            "nome": vereador.nome,
            "foto": vereador.foto.url if vereador.foto else "/static/img/default.jpg",
            "presente": vereador.presente,
            "voto": voto if (pauta and pauta.votacao_aberta) else "🔒 Voto Secreto"
        })

    return vereadores_data

from django.http import JsonResponse
from .models import Sessao, Pauta, Vereador, Votacao

def api_painel_publico(request):
    sessao = Sessao.objects.filter(status="Em Andamento").first()

    if not sessao:
        return JsonResponse({
            "sessao": {"nome": "Nenhuma sessão ativa", "descricao": "", "status": "Arquivada"},
            "pauta": {"titulo": "Nenhuma pauta em votação", "descricao": "", "status": "Aguardando", "tipo_votacao": ""},
            "vereadores": listar_vereadores(),
            "votos_sim": 0, "votos_nao": 0, "votos_abstencao": 0
        })

    pauta = Pauta.objects.filter(sessao=sessao, status="Em Votação").first()
    vereadores_data = listar_vereadores(pauta)

    if pauta:
        votos_sim = Votacao.objects.filter(pauta=pauta, voto="Sim").count()
        votos_nao = Votacao.objects.filter(pauta=pauta, voto="Não").count()
        votos_abstencao = Votacao.objects.filter(pauta=pauta, voto="Abstenção").count()
        tipo_votacao = pauta.tipo_votacao  # Define o tipo de votação
    else:
        votos_sim = votos_nao = votos_abstencao = 0
        tipo_votacao = ""

    if pauta and not pauta.votacao_aberta:
        for vereador in vereadores_data:
            vereador["voto"] = "🔒 Voto Secreto"

    vereadores_presentes = Vereador.objects.filter(votacao__pauta=None, votacao__presenca=True).exclude(funcao="Presidente").count()

    # **Definição da maioria conforme o tipo de votação**
    if pauta and pauta.tipo_votacao == "Qualificada":
        maioria = (2 * vereadores_presentes) // 3  # Maioria de 2/3
    else:
        maioria = (vereadores_presentes // 2) + 1 if vereadores_presentes > 1 else 1  # Maioria simples

    total_votantes = votos_sim + votos_nao + votos_abstencao
    todos_votaram = total_votantes >= vereadores_presentes

    status_pauta = "Aguardando votação"
    if pauta:
        status_pauta = "Em Votação"

    if pauta and todos_votaram:
        if votos_sim >= maioria:
            status_pauta = "Aprovada ✅"
            pauta.status = "Aprovada"
            pauta.save()
        elif votos_nao >= maioria:
            status_pauta = "Rejeitada ❌"
            pauta.status = "Rejeitada"
            pauta.save()
        elif votos_sim == votos_nao:
            presidente = Vereador.objects.filter(funcao="Presidente").first()
            presidente_votou = Votacao.objects.filter(pauta=pauta, vereador=presidente).exists() if presidente else False

            if not presidente_votou:
                status_pauta = "Aguardando Votação"
            else:
                if votos_sim > votos_nao:
                    status_pauta = "Aprovada ✅"
                    pauta.status = "Aprovada"
                else:
                    status_pauta = "Rejeitada ❌"
                    pauta.status = "Rejeitada"
                pauta.save()

    descricao_sessao = getattr(sessao, "descricao", "Sem descrição disponível")

    return JsonResponse({
        "sessao": {
            "nome": sessao.nome,
            "descricao": descricao_sessao,
            "status": sessao.status  # Agora incluímos o status da sessão
        },
        "pauta": {
            "titulo": pauta.titulo if pauta else "Nenhuma pauta em votação",
            "descricao": pauta.descricao if pauta else "",
            "status": status_pauta,
            "votacao_aberta": pauta.votacao_aberta if pauta else True,
            "tipo_votacao": tipo_votacao  # Retorna se é comum ou qualificada
        },
        "vereadores": vereadores_data,
        "votos_sim": votos_sim,
        "votos_nao": votos_nao,
        "votos_abstencao": votos_abstencao
    })


# 🔹 **Função para listar vereadores SEMPRE**
def listar_vereadores(pauta=None):
    vereadores_data = []
    vereadores = Vereador.objects.all()  # 🔹 Pegamos todos os vereadores, sempre
    for vereador in vereadores:
        voto = Votacao.objects.filter(vereador=vereador, pauta=pauta).first() if pauta else None
        vereadores_data.append({
            "nome": vereador.nome,
            "foto": vereador.foto.url if vereador.foto else "/static/img/default.png",
            "presente": Votacao.objects.filter(vereador=vereador, pauta=None, presenca=True).exists(),
            "voto": voto.voto if voto else "Nenhum"
        })
    return vereadores_data


    return JsonResponse({
        "sessao": {"nome": sessao.nome, "descricao": descricao_sessao},
        "pauta": {
            "titulo": pauta.titulo if pauta else "Nenhuma pauta em votação",
            "descricao": pauta.descricao if pauta else "",
            "status": status_pauta
        } if pauta else None,
        "vereadores": vereadores_data,
        "votos_sim": votos_sim,
        "votos_nao": votos_nao,
        "votos_abstencao": votos_abstencao
    })


def painel_publico(request):
    """
    Exibe o painel público com a votação em tempo real, garantindo que os tipos de votação
    e a visibilidade dos votos sejam corretamente refletidos.
    """

    # Buscar a sessão ativa (Em Andamento)
    sessao = Sessao.objects.filter(status="Em Andamento").first()

    # Se não houver sessão ativa, renderizar com valores padrão
    if not sessao:
        return render(
            request,
            "core/painel_publico.html",
            {
                "sessao": None,
                "pauta": None,
                "vereadores": [],
                "votos_sim": 0,
                "votos_nao": 0,
                "votos_abstencao": 0,
                "sessao_aberta": False,
                "tipo_votacao": None,
                "votacao_aberta": None,
            }
        )

    # Buscar a pauta que está em votação na sessão ativa
    pauta = Pauta.objects.filter(sessao=sessao, status="Em Votação").first()

    # Buscar todos os vereadores e verificar presença
    vereadores = Vereador.objects.all()
    for vereador in vereadores:
        vereador.presente = Votacao.objects.filter(vereador=vereador, pauta=None, presenca=True).exists()

    # Se não houver pauta em votação, definir valores padrão para evitar erro
    if not pauta:
        return render(
            request,
            "core/painel_publico.html",
            {
                "sessao": sessao,
                "pauta": None,
                "vereadores": vereadores,
                "votos_sim": 0,
                "votos_nao": 0,
                "votos_abstencao": 0,
                "sessao_aberta": True,
                "tipo_votacao": None,
                "votacao_aberta": None,
            }
        )

    # Buscar os votos da pauta em votação
    votos_sim = Votacao.objects.filter(pauta=pauta, voto="Sim").count()
    votos_nao = Votacao.objects.filter(pauta=pauta, voto="Não").count()
    votos_abstencao = Votacao.objects.filter(pauta=pauta, voto="Abstenção").count()

    # Tipo de votação (Simples, Absoluta, Qualificada)
    tipo_votacao = pauta.tipo_votacao

    # Verifica se a votação é aberta ou fechada
    votacao_aberta = pauta.votacao_aberta

    # Garante que os votos só são exibidos se a votação for aberta
    votos_sim_exibido = votos_sim if votacao_aberta else "Oculto"
    votos_nao_exibido = votos_nao if votacao_aberta else "Oculto"
    votos_abstencao_exibido = votos_abstencao if votacao_aberta else "Oculto"

    # Enviar os dados para o template
    context = {
        "sessao": sessao,
        "pauta": pauta,
        "vereadores": vereadores,
        "votos_sim": votos_sim_exibido,
        "votos_nao": votos_nao_exibido,
        "votos_abstencao": votos_abstencao_exibido,
        "sessao_aberta": True,
        "tipo_votacao": tipo_votacao,
        "votacao_aberta": votacao_aberta,
    }

    return render(request, "core/painel_publico.html", context)


def api_vereadores_presencas(request):
    # Buscar a sessão ativa
    sessao = Sessao.objects.filter(status="Em Andamento").first()

    # Retornar JSON vazio se não houver sessão ativa
    if not sessao:
        return JsonResponse({"message": "Nenhuma sessão ativa no momento", "vereadores": []})

    # Buscar todos os vereadores e verificar presença
    vereadores_data = []
    vereadores = Vereador.objects.all()
    for vereador in vereadores:
        presente = Votacao.objects.filter(vereador=vereador, pauta=None, presenca=True).exists()
        vereadores_data.append({
            "nome": vereador.nome,
            "foto": vereador.foto.url if vereador.foto else "/static/img/default.png",
            "presente": presente
        })

    return JsonResponse({"sessao": {"nome": sessao.nome}, "vereadores": vereadores_data})


def calcular_resultado_pauta(pauta):
    # Pega todos os votos registrados para a pauta
    votos_sim = Votacao.objects.filter(pauta=pauta, voto="Sim").count()
    votos_nao = Votacao.objects.filter(pauta=pauta, voto="Não").count()
    
    # Conta quantos vereadores estavam presentes
    vereadores_presentes = Votacao.objects.filter(pauta=None, presenca=True).count()
    
    # Verifica maioria simples
    maioria_simples = (vereadores_presentes // 2) + 1  # Metade + 1 para maioria

    if votos_sim > votos_nao:
        pauta.status = "Aprovada"
    elif votos_nao > votos_sim:
        pauta.status = "Rejeitada"
    else:
        pauta.status = "Empate - Aguardando voto do presidente"

    pauta.save()
    return pauta.status

def atualizar_status_pauta(pauta_id):
    pauta = get_object_or_404(Pauta, id=pauta_id)

    # Contagem de votos
    votos_sim = Votacao.objects.filter(pauta=pauta, voto="Sim").count()
    votos_nao = Votacao.objects.filter(pauta=pauta, voto="Não").count()
    votos_abstencao = Votacao.objects.filter(pauta=pauta, voto="Abstenção").count()

    total_votantes = votos_sim + votos_nao + votos_abstencao
    maioria = (total_votantes // 2) + 1  # Maioria simples

    # Atualizar o status da pauta
    if votos_sim >= maioria:
        pauta.status = "Aprovada"
    elif votos_nao >= maioria:
        pauta.status = "Rejeitada"
    
    pauta.save()  # Salvar a alteração no banco de dados

def visualizar_pautas(request):
    pautas = Pauta.objects.all()  # Pega todas as pautas disponíveis
    return render(request, 'core/visualizar_pautas.html', {'pautas': pautas})

def sessoes_encerradas(request):
    """ Exibe apenas as sessões encerradas para reabertura ou visualização do relatório. """
    sessoes = Sessao.objects.filter(status="Arquivada").order_by("-data")
    return render(request, "core/sessoes_encerradas.html", {"sessoes": sessoes})

def reabrir_sessao(request, sessao_id):
    """ Reabre uma sessão arquivada. """
    sessao = get_object_or_404(Sessao, id=sessao_id)

    if sessao.status == "Arquivada":
        sessao.status = "Em Andamento"
        sessao.save()
        messages.success(request, f"📌 Sessão {sessao.nome} foi reaberta!")

    return redirect("painel_presidente")

def gerar_relatorio_presencas(request, sessao_id):
    """ Gera um relatório em PDF das presenças registradas na sessão encerrada. """

    # Obtém a sessão
    sessao = Sessao.objects.get(id=sessao_id)

    # Obtém os vereadores presentes a partir da tabela correta
    vereadores_presentes = PresencaRegistrada.objects.filter(sessao=sessao).values_list("vereador__nome", flat=True)

    # Configura a resposta HTTP para PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="presencas_sessao_{sessao.id}.pdf"'

    # Criar o documento PDF
    doc = SimpleDocTemplate(response, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    # 🔹 Estilos personalizados
    left_aligned_style = ParagraphStyle(name="LeftAligned", parent=styles["Normal"], alignment=0)
    centered_style = ParagraphStyle(name="CenteredTitle", parent=styles["Normal"], alignment=1, fontSize=14, spaceAfter=12, fontName="Helvetica-Bold")

    # 🔹 Cabeçalho com Logo e Informações da Câmara
    câmara_nome = "Câmara Municipal de Wanderlândia"
    câmara_endereco = "Av. Gomes Ferreira, 564 - Centro, Wanderlândia/TO"
    câmara_cnpj = "CNPJ: 00.237.271/0001-65"

    # 🔹 Caminho da logo
    logo_path = os.path.join(settings.BASE_DIR, 'core', 'static', 'logo.png')

    if os.path.exists(logo_path):
        img = Image(logo_path, width=100, height=100)
        elements.append(img)
    else:
        elements.append(Paragraph("LOGO NÃO DISPONÍVEL", left_aligned_style))

    elements.append(Paragraph(f"<b>{câmara_nome}</b>", left_aligned_style))
    elements.append(Paragraph(f"{câmara_endereco}", left_aligned_style))
    elements.append(Paragraph(f"{câmara_cnpj}", left_aligned_style))
    elements.append(Spacer(1, 15))

    # 🔹 Informações da Sessão
    elements.append(Paragraph(f"<b>Relatório de Presença - Sessão:</b> {sessao.nome}", left_aligned_style))
    elements.append(Paragraph(f"Data: {sessao.data.strftime('%d/%m/%Y')}", left_aligned_style))
    elements.append(Paragraph(f"Horário: {sessao.hora.strftime('%H:%M')}", left_aligned_style))
    elements.append(Paragraph(f"Status: {sessao.status}", left_aligned_style))
    elements.append(Spacer(1, 30))  # 🔹 Adiciona mais espaço

    # 🔹 Título centralizado para vereadores presentes
    elements.append(Paragraph("<b>Vereadores Presentes</b>", centered_style))
    elements.append(Spacer(1, 15))  # 🔹 Espaço entre o título e a tabela

    # 🔹 Tabela de presença com linha para assinatura
    if vereadores_presentes:
        presenca_data = [["Vereador", "Assinatura"]]
        for vereador in vereadores_presentes:
            presenca_data.append([vereador, "_______________________________________"])  # Linha para assinatura
        
        tabela_presencas = Table(presenca_data, colWidths=[3.5 * inch, 3.5 * inch])
        tabela_presencas.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(tabela_presencas)
    else:
        elements.append(Paragraph("Nenhum vereador registrou presença.", left_aligned_style))

    # Gera o PDF
    doc.build(elements)
    return response

def pautas_do_dia(request):
    vereador_id = request.session.get("vereador_id")
    if not vereador_id:
        return redirect("login")

    sessoes = Sessao.objects.filter(status="Em Andamento")
    pautas = Pauta.objects.filter(sessao__in=sessoes)

    # Adiciona contagem de votos para cada pauta
    for pauta in pautas:
        pauta.votos_sim = Votacao.objects.filter(pauta=pauta, voto="Sim").count()
        pauta.votos_nao = Votacao.objects.filter(pauta=pauta, voto="Não").count()
        pauta.votos_abstencao = Votacao.objects.filter(pauta=pauta, voto="Abstenção").count()

    return render(request, 'core/pautas_do_dia.html', {'pautas': pautas})

def api_pautas_do_dia(request):
    sessoes = Sessao.objects.filter(status="Em Andamento")
    pautas = Pauta.objects.filter(sessao__in=sessoes)

    pautas_data = []
    for pauta in pautas:
        pautas_data.append({
            "id": pauta.id,
            "votos_sim": Votacao.objects.filter(pauta=pauta, voto="Sim").count(),
            "votos_nao": Votacao.objects.filter(pauta=pauta, voto="Não").count(),
            "votos_abstencao": Votacao.objects.filter(pauta=pauta, voto="Abstenção").count(),
        })

    return JsonResponse({"pautas": pautas_data})


def iniciar_votacao(request, pauta_id, tipo_votacao, modalidade):
    """
    Inicia a votação para uma pauta, aplicando o tipo de votação definido pelo presidente.
    """
    pauta = get_object_or_404(Pauta, id=pauta_id)

    # ✅ Define se a votação será aberta ou fechada
    pauta.votacao_aberta = True if tipo_votacao == "aberta" else False
    pauta.tipo_votacao = modalidade  # ✅ Define se a votação será simples, absoluta ou qualificada
    pauta.status = "Em Votação"
    pauta.save()

    messages.success(request, f"🗳️ Votação {modalidade.upper()} foi iniciada como {tipo_votacao.upper()}!")
    return redirect("painel_presidente")

def listar_relatorios(request):
    """
    Lista todas as sessões ARQUIVADAS para consulta pública de relatórios.
    """
    sessoes_arquivadas = Sessao.objects.filter(status="Arquivada").order_by('-data')

    return render(request, "core/listar_relatorios.html", {"sessoes": sessoes_arquivadas})

def criar_superusuario(request):
    if not User.objects.filter(username="admin").exists():
        User.objects.create_superuser("admin", "admin@email.com", "senha123")
        return HttpResponse("Superusuário criado com sucesso!")
    else:
        return HttpResponse("Superusuário já existe!")





