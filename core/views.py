# views.py - Desenvolvimento dos Painéis do Vereador e Presidente

from django.shortcuts import render, redirect, get_object_or_404
from django.utils.timezone import now
from .models import Sessao, Vereador, Pauta, Votacao, Cronometro, Relatorio, CamaraMunicipal
from django.http import HttpResponse
from django.template.loader import render_to_string
import tempfile
import os
from django.conf import settings
from .forms import PautaForm
from django.utils import timezone
from .models import Live  # Importando a classe Live (se ela for um modelo)
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
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from .forms import SessaoForm, PautaForm, VereadorForm, CamaraMunicipalForm






def login_view(request):
    camara = CamaraMunicipal.objects.first()  # pega os dados da câmara (logo e papel de parede)

    if request.method == "POST":
        cpf = request.POST.get("cpf")
        senha = request.POST.get("senha")

        print(f"Tentativa de login com CPF: {cpf} e Senha: {senha}")

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
            return render(
                request,
                "core/login.html",
                {"erro": "CPF ou senha incorretos", "camara": camara}
            )

    return render(request, "core/login.html", {"camara": camara})


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

    camara = CamaraMunicipal.objects.first()  # ✅ adiciona a câmara

    return render(request, "core/painel_vereador.html", {
        "vereador": vereador,
        "pautas": pautas,
        "sessao_ativa": sessao_ativa,
        "votos_realizados": votos_realizados,
        "camara": camara,  # ✅ envia para o template
    })




def painel_presidente(request):
    vereador_id = request.session.get("vereador_id")
    if not vereador_id:
        return redirect("login")

    presidente = get_object_or_404(Vereador, id=vereador_id, funcao='Presidente')

    # 🔹 Sessões que NÃO estão arquivadas
    sessoes_ativas = Sessao.objects.exclude(status='Arquivada')

    # 🔹 Busca a câmara municipal (pode ajustar esse filtro se houver mais de uma)
    camara = CamaraMunicipal.objects.first()

    return render(request, 'core/painel_presidente.html', {
        'presidente': presidente,
        'sessoes': sessoes_ativas,
        'camara': camara,  # Envia a câmara para o template
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
    sessao = get_object_or_404(Sessao, id=sessao_id)
    pautas = Pauta.objects.filter(sessao=sessao)
    votos = Votacao.objects.filter(pauta__in=pautas)
    camara = CamaraMunicipal.objects.first()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="relatorio_sessao_{sessao.id}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    # Estilos personalizados
    left_aligned = ParagraphStyle(name="LeftAligned", parent=styles["Normal"], alignment=0)
    centered = ParagraphStyle(name="Centered", parent=styles["Normal"], alignment=1)
    titulo_grande = ParagraphStyle(name="TituloGrande", parent=styles["Heading1"], fontSize=16, alignment=1)

    # 🔹 LOGO da Câmara via Cloudinary
    if camara and camara.logo:
        try:
            logo_url, _ = cloudinary_url(camara.logo.public_id, format="png")
            with urllib.request.urlopen(logo_url) as url:
                logo_data = io.BytesIO(url.read())
                img = Image(ImageReader(logo_data), width=80, height=80)
                img.hAlign = "CENTER"
                elements.append(img)
        except Exception:
            elements.append(Paragraph("LOGO NÃO DISPONÍVEL", centered))
    else:
        elements.append(Paragraph("LOGO NÃO DISPONÍVEL", centered))

    # 🔹 Nome e dados da Câmara
    if camara:
        endereco_formatado = f"{camara.endereco or ''}, {camara.numero or ''} - {camara.cidade or ''}/{camara.uf or ''}"
        elements.append(Paragraph(f"<b>{camara.nome}</b>", titulo_grande))
        elements.append(Paragraph(endereco_formatado, centered))
        elements.append(Paragraph(f"CNPJ: {camara.cnpj or 'Não informado'}", centered))
    else:
        elements.append(Paragraph("Informações da Câmara não cadastradas.", centered))

    elements.append(Spacer(1, 20))

    # 🔹 Informações da Sessão
    elements.append(Paragraph(f"<b>Relatório da Sessão:</b> {sessao.nome}", left_aligned))
    elements.append(Paragraph(f"Data: {sessao.data.strftime('%d/%m/%Y')}", left_aligned))
    elements.append(Paragraph(f"Horário: {sessao.hora.strftime('%H:%M')}", left_aligned))
    elements.append(Paragraph(f"Status: {sessao.status}", left_aligned))
    elements.append(Spacer(1, 15))

    # 🔹 Pautas e votos
    for pauta in pautas:
        elements.append(Paragraph(f"<b>Pauta:</b> {pauta.titulo}", left_aligned))
        elements.append(Paragraph(f"<b>Tipo:</b> {pauta.tipo}", left_aligned))
        elements.append(Paragraph(f"<b>Autor:</b> {pauta.autor.nome}", left_aligned))
        elements.append(Paragraph(f"<b>Status:</b> {pauta.status}", left_aligned))

        tipo_txt = {
            "simples": "Maioria Simples",
            "absoluta": "Maioria Absoluta",
            "qualificada": "Maioria Qualificada (2/3)"
        }.get(pauta.tipo_votacao, "Não definido")

        elements.append(Paragraph(f"<b>Tipo de Votação:</b> {tipo_txt}", left_aligned))
        elements.append(Paragraph(f"<b>Votação:</b> {'Aberta' if pauta.votacao_aberta else 'Secreta'}", left_aligned))
        elements.append(Spacer(1, 10))

        votos_pauta = votos.filter(pauta=pauta)
        votos_sim = votos_pauta.filter(voto="Sim").count()
        votos_nao = votos_pauta.filter(voto="Não").count()
        votos_abs = votos_pauta.filter(voto="Abstenção").count()

        if pauta.votacao_aberta:
            if votos_pauta.exists():
                data = [["Vereador", "Voto"]]
                for voto in votos_pauta:
                    data.append([voto.vereador.nome, voto.voto])

                tabela = Table(data, colWidths=[3 * inch, 2 * inch])
                tabela.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                elements.append(tabela)
            else:
                elements.append(Paragraph("Nenhum voto registrado para esta pauta.", left_aligned))
        else:
            elements.append(Paragraph("Votação secreta - Nomes ocultados", left_aligned))

        elements.append(Spacer(1, 10))
        elements.append(Paragraph(f"<b>Totais:</b> Sim: {votos_sim} | Não: {votos_nao} | Abstenção: {votos_abs}", centered))
        elements.append(Spacer(1, 20))

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

@login_required
def editar_pauta(request, pauta_id):
    pauta = get_object_or_404(Pauta, id=pauta_id)

    if request.method == "POST":
        form = PautaForm(request.POST, instance=pauta)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Pauta atualizada com sucesso!")
            return redirect("listar_pautas")  # ✅ redireciona para listagem
    else:
        form = PautaForm(instance=pauta)

    return render(request, "cadastros/form_pauta.html", {
        "form": form,
        "pauta": pauta,
        "edicao": True  # opcional: usar no template para exibir "Editar Pauta"
    })

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
            "votos_sim": 0,
            "votos_nao": 0,
            "votos_abstencao": 0,
            "autor_pauta": None,
        })

    pauta = Pauta.objects.filter(sessao=sessao, status="Em Votação").first()
    if not pauta:
        pauta = Pauta.objects.filter(sessao=sessao, status__in=["Aprovada", "Rejeitada"]).order_by("-atualizado_em").first()

    if not pauta:
        return JsonResponse({
            "sessao": {"nome": sessao.nome, "descricao": getattr(sessao, "descricao", ""), "status": sessao.status},
            "pauta": {"titulo": "Nenhuma pauta em votação", "descricao": "", "status": "Aguardando", "tipo_votacao": ""},
            "vereadores": listar_vereadores(),
            "votos_sim": 0,
            "votos_nao": 0,
            "votos_abstencao": 0,
            "autor_pauta": None,
        })

    vereadores_data = listar_vereadores(pauta)

    votos_sim = Votacao.objects.filter(pauta=pauta, voto="Sim").count()
    votos_nao = Votacao.objects.filter(pauta=pauta, voto="Não").count()
    votos_abstencao = Votacao.objects.filter(pauta=pauta, voto="Abstenção").count()

    tipo_votacao = pauta.tipo_votacao or ""

    if not pauta.votacao_aberta:
        for vereador in vereadores_data:
            vereador["voto"] = "🔒 Voto Secreto"

    presentes_ids = list(Votacao.objects.filter(pauta=None, presenca=True).values_list("vereador_id", flat=True))
    total_presentes = len(presentes_ids)

    presidente = Vereador.objects.filter(funcao="Presidente").first()
    presidente_presente = presidente and presidente.id in presentes_ids
    presidente_votou = Votacao.objects.filter(pauta=pauta, vereador=presidente).exists() if presidente else False

    vereadores_comuns_presentes = total_presentes - (1 if presidente_presente else 0)
    total_votantes = votos_sim + votos_nao + votos_abstencao

    maioria_simples = (vereadores_comuns_presentes // 2) + 1 if vereadores_comuns_presentes > 0 else 1
    maioria_qualificada = (2 * total_presentes + 2) // 3 if total_presentes > 0 else 1

    if pauta.status == "Em Votação":
        if tipo_votacao == "qualificada":
            if presidente_presente and not presidente_votou:
                pass
            elif total_votantes >= total_presentes:
                pauta.status = "Aprovada" if votos_sim >= maioria_qualificada else "Rejeitada"
                pauta.save()
        else:
            if total_votantes >= vereadores_comuns_presentes:
                if votos_sim > votos_nao:
                    pauta.status = "Aprovada"
                    pauta.save()
                elif votos_nao > votos_sim:
                    pauta.status = "Rejeitada"
                    pauta.save()
                elif votos_sim == votos_nao:
                    if presidente_presente and presidente_votou:
                        voto_presidente = Votacao.objects.filter(pauta=pauta, vereador=presidente).first()
                        if voto_presidente:
                            if voto_presidente.voto == "Sim":
                                pauta.status = "Aprovada"
                            else:
                                pauta.status = "Rejeitada"
                        pauta.save()

    status_display = {
        "Em Votação": "⛔ Em Votação",
        "Aprovada": "✅ Aprovada",
        "Rejeitada": "❌ Rejeitada"
    }.get(pauta.status, "⚠️ Aguardando votação")

    autor_data = {}
    if pauta and pauta.autor:
        autor_data = {
            "nome": pauta.autor.nome,
            "partido": pauta.autor.partido,
            "foto": pauta.autor.foto.url if pauta.autor.foto else ""
        }

    return JsonResponse({
        "sessao": {
            "nome": sessao.nome,
            "descricao": getattr(sessao, "descricao", ""),
            "status": sessao.status
        },
        "pauta": {
            "titulo": pauta.titulo,
            "descricao": pauta.descricao,
            "status": status_display,
            "votacao_aberta": pauta.votacao_aberta,
            "tipo_votacao": tipo_votacao
        },
        "vereadores": vereadores_data,
        "votos_sim": votos_sim,
        "votos_nao": votos_nao,
        "votos_abstencao": votos_abstencao,
        "autor_pauta": autor_data
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

    # Busca a única Câmara cadastrada
    camara = CamaraMunicipal.objects.first()

    # Buscar a sessão ativa (Em Andamento)
    sessao = Sessao.objects.filter(status="Em Andamento").first()

    # Se não houver sessão ativa, renderiza o screensaver com imagem da câmara
    if not sessao:
        return render(
            request,
            "core/painel_publico.html",
            {
                "camara": camara,  # envia imagem de fundo
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

    # Se não houver pauta em votação, exibe painel sem votação
    if not pauta:
        return render(
            request,
            "core/painel_publico.html",
            {
                "camara": camara,
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

    # Contagem dos votos
    votos_sim = Votacao.objects.filter(pauta=pauta, voto="Sim").count()
    votos_nao = Votacao.objects.filter(pauta=pauta, voto="Não").count()
    votos_abstencao = Votacao.objects.filter(pauta=pauta, voto="Abstenção").count()

    # Tipo e visibilidade da votação
    tipo_votacao = pauta.tipo_votacao
    votacao_aberta = pauta.votacao_aberta

    # Exibe os votos apenas se for votação aberta
    votos_sim_exibido = votos_sim if votacao_aberta else "Oculto"
    votos_nao_exibido = votos_nao if votacao_aberta else "Oculto"
    votos_abstencao_exibido = votos_abstencao if votacao_aberta else "Oculto"

    # Envia para o template
    context = {
        "camara": camara,
        "sessao": sessao,
        "pauta": pauta,
        "vereadores": vereadores,
        "votos_sim": votos_sim_exibido,
        "votos_nao": votos_nao_exibido,
        "votos_abstencao": votos_abstencao_exibido,
        "sessao_aberta": True,
        "tipo_votacao": tipo_votacao,
        "votacao_aberta": votacao_aberta,
        "camara": camara,
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
    sessao = Sessao.objects.get(id=sessao_id)
    vereadores_presentes = PresencaRegistrada.objects.filter(sessao=sessao).values_list("vereador__nome", flat=True)
    camara = CamaraMunicipal.objects.first()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="presencas_sessao_{sessao.id}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    # Estilos
    center = ParagraphStyle(name="Center", parent=styles["Normal"], alignment=1)
    bold_center = ParagraphStyle(name="BoldCenter", parent=styles["Heading2"], alignment=1, fontSize=14)

    # Logo (centralizada)
    if camara and camara.logo:
        try:
            with urllib.request.urlopen(camara.logo.url) as url:
                logo_data = io.BytesIO(url.read())
                img = Image(ImageReader(logo_data), width=80, height=80)
                img.hAlign = 'CENTER'
                elements.append(img)
        except Exception:
            elements.append(Paragraph("LOGO NÃO DISPONÍVEL", center))
    else:
        elements.append(Paragraph("LOGO NÃO DISPONÍVEL", center))

    # Informações da Câmara (centralizado)
    if camara:
        endereco_formatado = f"{camara.endereco or ''}, {camara.numero or ''} - {camara.cidade or ''}/{camara.uf or ''}"
        elements.append(Paragraph(f"<b>{camara.nome}</b>", bold_center))
        elements.append(Paragraph(endereco_formatado, center))
        elements.append(Paragraph(f"CNPJ: {camara.cnpj or 'Não informado'}", center))
    else:
        elements.append(Paragraph("Informações da Câmara não cadastradas.", center))

    elements.append(Spacer(1, 20))

    # Sessão
    elements.append(Paragraph(f"<b>Relatório de Presença - Sessão:</b> {sessao.nome}", center))
    elements.append(Paragraph(f"Data: {sessao.data.strftime('%d/%m/%Y')}", center))
    elements.append(Paragraph(f"Horário: {sessao.hora.strftime('%H:%M')}", center))
    elements.append(Paragraph(f"Status: {sessao.status}", center))
    elements.append(Spacer(1, 30))

    # Título da Tabela
    elements.append(Paragraph("<b>Vereadores Presentes</b>", bold_center))
    elements.append(Spacer(1, 15))

    # Tabela de presença
    if vereadores_presentes:
        data = [["Vereador", "Assinatura"]]
        for nome in vereadores_presentes:
            data.append([nome, "_______________________________________"])
        
        tabela = Table(data, colWidths=[3.5 * inch, 3.5 * inch])
        tabela.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(tabela)
    else:
        elements.append(Paragraph("Nenhum vereador registrou presença.", center))

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


def atualizar_botoes_voto(request):
    vereador_id = request.session.get("vereador_id")
    if not vereador_id:
        return JsonResponse({"html": ""})  # Usuário não autenticado como vereador

    vereador = Vereador.objects.get(id=vereador_id)
    pautas_em_votacao = Pauta.objects.filter(status="Em Votação")

    # Busca IDs das pautas já votadas por esse vereador
    votos_feitos = Votacao.objects.filter(vereador=vereador).values_list("pauta_id", flat=True)

    pautas_para_votar = [pauta for pauta in pautas_em_votacao if pauta.id not in votos_feitos]

    html = render_to_string("parciais/botoes_voto.html", {
        "pautas": pautas_para_votar,
        "vereador": vereador,
    }, request=request)

    return JsonResponse({"html": html})

def termos_de_uso(request):
    return render(request, 'core/termos_de_uso.html')

def cronometro_publico(request):
    try:
        cronometro = Cronometro.objects.filter(status='Iniciado').latest('data_inicio')
        vereador = cronometro.vereador
    except Cronometro.DoesNotExist:
        return redirect('painel_publico')  # <- se não tiver, volta pro painel normal

    sessao = Sessao.objects.filter(status="Em Andamento").first()

    return render(request, 'core/cronometro_publico.html', {
        'cronometro': cronometro,
        'vereador': vereador,
        'sessao': sessao
    })


def iniciar_cronometro(request, vereador_id):
    if request.method == "POST":
        try:
            tempo_padrao = 300  # 5 minutos
            agora = timezone.now()

            # Finaliza os cronômetros anteriores dos outros vereadores
            Cronometro.objects.exclude(vereador_id=vereador_id).update(
                status='Finalizado',
                tempo_restante=0,
                tempo_extra=0
            )

            # Tenta obter ou criar um novo cronômetro para o vereador
            cronometro, created = Cronometro.objects.get_or_create(
                vereador_id=vereador_id,
                defaults={
                    'tempo_inicial': tempo_padrao,
                    'tempo_restante': tempo_padrao,
                    'tempo_extra': 0,
                    'status': 'Iniciado',
                    'data_inicio': agora
                }
            )

            if not created:
                # Se o cronômetro não foi criado, atualiza o cronômetro existente
                if cronometro.status == 'Pausado':
                    cronometro.data_inicio = agora
                elif cronometro.status == 'Finalizado':
                    cronometro.tempo_restante = tempo_padrao
                    cronometro.tempo_extra = 0
                    cronometro.data_inicio = agora

                cronometro.status = 'Iniciado'
                cronometro.save()

            return JsonResponse({
                'status': cronometro.status,
                'tempo_restante': cronometro.tempo_restante,
                'tempo_extra': cronometro.tempo_extra,
                'message': 'Cronômetro iniciado com sucesso'
            })

        except Exception as e:
            print("ERRO AO INICIAR CRONÔMETRO:", e)
            return JsonResponse({'erro': str(e)}, status=500)

    return JsonResponse({'erro': 'Método não permitido'}, status=405)

# Pausar cronômetro
def pausar_cronometro(request, vereador_id):
    if request.method == "POST":
        cronometro = get_object_or_404(Cronometro, vereador_id=vereador_id)

        # Atualiza o tempo restante antes de pausar
        if cronometro.status == 'Iniciado':
            agora = timezone.now()
            segundos_passados = int((agora - cronometro.data_inicio).total_seconds())
            cronometro.tempo_restante = max(0, cronometro.tempo_restante - segundos_passados)

        cronometro.status = 'Pausado'
        cronometro.save()
        return JsonResponse({'status': 'pausado'})




# Parar cronômetro
def parar_cronometro(request, vereador_id):
    if request.method == "POST":
        cronometro = get_object_or_404(Cronometro, vereador_id=vereador_id)
        cronometro.status = 'Finalizado'
        cronometro.tempo_restante = 0
        cronometro.tempo_extra = 0
        cronometro.save()
        return JsonResponse({'status': 'finalizado'})
    return JsonResponse({'erro': 'Método não permitido'}, status=405)


# Adicionar +1 minuto de tempo extra
def adicionar_tempo(request, vereador_id):
    cronometro = get_object_or_404(Cronometro, vereador_id=vereador_id)
    cronometro.tempo_restante += 60
    cronometro.tempo_extra += 60
    cronometro.save()
    return JsonResponse({
        'status': 'tempo_adicionado',
        'tempo_restante': cronometro.tempo_restante,
        'tempo_extra': cronometro.tempo_extra,
    })

def painel_cronometro(request):
    vereadores = Vereador.objects.all()  # Busca todos os vereadores
    live = Live.objects.first()  # Pega a primeira live cadastrada (se houver)

    return render(request, 'core/painel_cronometro.html', {
        'vereadores': vereadores,
        'live_link': live.link if live else None  # Passa o link da live, se existir
    })

def tempo_restante(request, vereador_id):
    cronometro = get_object_or_404(Cronometro, vereador_id=vereador_id)

    if cronometro.status == 'Iniciado':
        agora = timezone.now()
        segundos_passados = int((agora - cronometro.data_inicio).total_seconds())
        tempo_atualizado = cronometro.tempo_restante - segundos_passados

        if tempo_atualizado < 0:
            tempo_atualizado = 0
            cronometro.status = 'Finalizado'
        
        return JsonResponse({
            'tempo_restante': tempo_atualizado,
            'status': cronometro.status
        })

    return JsonResponse({
        'tempo_restante': cronometro.tempo_restante,
        'status': cronometro.status
    })


def api_cronometro_ativo(request):
    try:
        cronometro = Cronometro.objects.get(status='Iniciado')
        agora = timezone.now()
        segundos_passados = int((agora - cronometro.data_inicio).total_seconds())
        tempo_atualizado = cronometro.tempo_restante - segundos_passados

        if tempo_atualizado <= 0:
            tempo_atualizado = 0
            cronometro.status = 'Finalizado'
            cronometro.save()

        vereador = cronometro.vereador

        return JsonResponse({
            'vereador_nome': vereador.nome,
            'vereador_partido': vereador.partido,
            'vereador_funcao': vereador.funcao,
            'vereador_foto': vereador.foto.url if vereador.foto else '',
            'tempo_restante': tempo_atualizado,
            'tempo_extra': cronometro.tempo_extra,
            'status': cronometro.status,
        })
    except Cronometro.DoesNotExist:
        return JsonResponse({
            'tempo_restante': 0,
            'status': 'Finalizado',
        })
    
def api_sessao_ativa(request):
    # Buscar a sessão ativa mais recente que não está encerrada
    sessao = Sessao.objects.filter(status='Em Andamento', data_hora__lte=timezone.now()).order_by('-data_hora').first()
    
    if sessao:
        # Se a sessão estiver ativa, retorna o nome da sessão
        return JsonResponse({"nome": sessao.nome})
    else:
        # Se não houver sessão ativa, retorna "Em Andamento"
        return JsonResponse({"nome": "Em Andamento"})


def login_usuario(request):
    if request.method == 'POST':
        username = request.POST['username']
        senha = request.POST['senha']
        user = authenticate(request, username=username, password=senha)
        if user is not None:
            login(request, user)
            return redirect('painel_cadastros')
        else:
            return render(request, 'login.html', {'erro': 'Usuário ou senha inválidos'})
    return render(request, 'login.html')

def logout_usuario(request):
    logout(request)
    return redirect('login')

@login_required
def painel_cadastros(request):
    return render(request, 'cadastros/painel_cadastros.html')

@login_required
def cadastrar_sessao(request):
    form = SessaoForm(request.POST or None)
    if form.is_valid():
        form.save()
        return render(request, 'cadastros/confirmacao.html')
    return render(request, 'cadastros/form_sessao.html', {'form': form})

@login_required
def cadastrar_pauta(request):
    form = PautaForm(request.POST or None)
    if form.is_valid():
        form.save()
        return render(request, 'cadastros/confirmacao.html')
    return render(request, 'cadastros/form_pauta.html', {'form': form})

@login_required
def cadastrar_vereador(request):
    form = VereadorForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        form.save()
        return render(request, 'cadastros/confirmacao.html')
    return render(request, 'cadastros/form_vereador.html', {'form': form})

@login_required
def cadastrar_camara(request):
    form = CamaraMunicipalForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        form.save()
        return render(request, 'cadastros/confirmacao.html')
    return render(request, 'cadastros/form_camara.html', {'form': form})

def login_admin(request):
    if request.method == 'POST':
        username = request.POST['username']
        senha = request.POST['senha']
        user = authenticate(request, username=username, password=senha)
        if user is not None and (user.is_staff or user.is_superuser):
            login(request, user)
            return redirect('painel_cadastros')
        else:
            return render(request, 'cadastros/login_admin.html', {'erro': 'Acesso não autorizado.'})
    return render(request, 'cadastros/login_admin.html')

@login_required
def listar_vereadores_view(request):
    vereadores = Vereador.objects.all()
    return render(request, 'cadastros/listar_vereadores.html', {'vereadores': vereadores})

@login_required
def listar_sessoes(request):
    sessoes = Sessao.objects.all()
    return render(request, 'cadastros/listar_sessoes.html', {'sessoes': sessoes})

@login_required
def listar_pautas(request):
    pautas = Pauta.objects.all()
    return render(request, 'cadastros/listar_pautas.html', {'pautas': pautas})

@login_required
def editar_vereador(request, vereador_id):
    vereador = get_object_or_404(Vereador, id=vereador_id)
    form = VereadorForm(request.POST or None, request.FILES or None, instance=vereador)
    if form.is_valid():
        form.save()
        return redirect('listar_vereadores')
    return render(request, 'cadastros/form_vereador.html', {'form': form})

@login_required
def dados_camara(request):
    camara = CamaraMunicipal.objects.first()
    return render(request, 'cadastros/dados_camara.html', {'camara': camara})

@login_required
def editar_sessao(request, sessao_id):
    sessao = get_object_or_404(Sessao, id=sessao_id)
    form = SessaoForm(request.POST or None, instance=sessao)
    if form.is_valid():
        form.save()
        return redirect('listar_sessoes')  # volta pra lista depois de editar
    return render(request, 'cadastros/form_sessao.html', {'form': form})
