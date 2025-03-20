from django.test import TestCase
from django.utils import timezone
from .models import Vereador, Sessao, Pauta, Votacao

class VotacaoTestCase(TestCase):
    def setUp(self):
        """ Configuração inicial para os testes """
        self.sessao = Sessao.objects.create(
            nome="Sessão Teste",
            data=timezone.now().date(),
            hora=timezone.now().time(),
            status="Em Andamento"
        )

        # Criando 9 vereadores e marcando presença
        self.vereadores = []
        for i in range(9):
            vereador = Vereador.objects.create(
                nome=f"Vereador {i+1}",
                apelido=f"V{i+1}",
                cpf=f"000000000{i}",
                email=f"vereador{i+1}@email.com",
                telefone="999999999",
                partido="Partido X",
                senha="senha123",
                funcao="Vereador",
                status="Ativo"
            )
            self.vereadores.append(vereador)
            self.sessao.vereadores_presentes.add(vereador)  # Adiciona presença

        self.pauta = Pauta.objects.create(
            titulo="Projeto de Lei Teste",
            descricao="Teste de votação",
            data=timezone.now().date(),
            hora=timezone.now().time(),
            autor=self.vereadores[0],
            tipo="Projeto de Lei",
            sessao=self.sessao,
            origem="Legislativo",
            status="Em Votação",
            votacao_aberta=True
        )

    def votar(self, votos):
        """ Simula votos dos vereadores """
        for vereador, voto in zip(self.vereadores, votos):
            Votacao.objects.create(vereador=vereador, pauta=self.pauta, voto=voto)

    def test_votacao_simples_aprovada(self):
        self.pauta.tipo_votacao = "simples"
        self.pauta.save()
        self.votar(['Sim', 'Sim', 'Sim', 'Sim', 'Sim', 'Não', 'Não', 'Abstenção', 'Abstenção'])
        self.pauta.definir_resultado()
        self.assertEqual(self.pauta.status, "Aprovada")

    def test_votacao_simples_rejeitada(self):
        self.pauta.tipo_votacao = "simples"
        self.pauta.save()
        self.votar(['Não', 'Não', 'Não', 'Não', 'Não', 'Sim', 'Sim', 'Abstenção', 'Abstenção'])
        self.pauta.definir_resultado()
        self.assertEqual(self.pauta.status, "Rejeitada")

    def test_votacao_absoluta_aprovada(self):
        self.pauta.tipo_votacao = "absoluta"
        self.pauta.save()
        self.votar(['Sim', 'Sim', 'Sim', 'Sim', 'Sim', 'Não', 'Não', 'Não', 'Abstenção'])
        self.pauta.definir_resultado()
        self.assertEqual(self.pauta.status, "Aprovada")

    def test_votacao_absoluta_rejeitada(self):
        self.pauta.tipo_votacao = "absoluta"
        self.pauta.save()
        self.votar(['Não', 'Não', 'Não', 'Não', 'Não', 'Sim', 'Sim', 'Sim', 'Abstenção'])
        self.pauta.definir_resultado()
        self.assertEqual(self.pauta.status, "Rejeitada")

    def test_votacao_qualificada_aprovada(self):
        self.pauta.tipo_votacao = "qualificada"
        self.pauta.save()
        self.votar(['Sim', 'Sim', 'Sim', 'Sim', 'Sim', 'Sim', 'Não', 'Não', 'Abstenção'])
        self.pauta.definir_resultado()
        self.assertEqual(self.pauta.status, "Aprovada")

    def test_votacao_qualificada_rejeitada(self):
        self.pauta.tipo_votacao = "qualificada"
        self.pauta.save()
        self.votar(['Não', 'Não', 'Não', 'Não', 'Não', 'Sim', 'Sim', 'Sim', 'Sim'])
        self.pauta.definir_resultado()
        self.assertEqual(self.pauta.status, "Rejeitada")
