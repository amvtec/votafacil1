from django.db import models

# Modelos de Vereador
class Vereador(models.Model):
    nome = models.CharField(max_length=100)
    apelido = models.CharField(max_length=100)
    cpf = models.CharField(max_length=11)
    email = models.EmailField()
    telefone = models.CharField(max_length=15)
    partido = models.CharField(max_length=50)
    senha = models.CharField(max_length=100)
    foto = models.ImageField(upload_to='fotos_vereadores/')
    funcao = models.CharField(max_length=50, choices=[('Vereador', 'Vereador'), ('Presidente', 'Presidente'), ('Vice-Presidente', 'Vice-Presidente'), ('Primeiro Secretário', 'Primeiro Secretário')])
    status = models.CharField(max_length=10, choices=[('Ativo', 'Ativo'), ('Inativo', 'Inativo')])
    
    def __str__(self):
        return self.nome


# Modelos de Sessão
from django.db import models

class Sessao(models.Model):
    nome = models.CharField(max_length=100)
    data = models.DateField()
    hora = models.TimeField()
    arquivada = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20, 
        choices=[('Em Andamento', 'Em Andamento'), ('Arquivada', 'Arquivada')]
    )
    vereadores_presentes = models.ManyToManyField("Vereador", blank=True)  # ✅ Adicionado
    encerrada_em = models.DateTimeField(null=True, blank=True)  # ✅ Novo campo para armazenar a data e hora do encerramento

    def __str__(self):
        return self.nome



from django.utils import timezone


from django.db import models

from django.db import models

class Pauta(models.Model):
    ORIGEM_CHOICES = [
        ('Executivo', 'Executivo'),
        ('Legislativo', 'Legislativo'),
    ]

    STATUS_CHOICES = [
        ('Em Espera', 'Em Espera'),
        ('Em Votação', 'Em Votação'),
        ('Aprovada', 'Aprovada'),
        ('Rejeitada', 'Rejeitada'),
        ('Encerrada', 'Encerrada'),
    ]

    TIPOS_VOTACAO = [
        ('simples', 'Maioria Simples'),
        ('absoluta', 'Maioria Absoluta'),
        ('qualificada', 'Maioria Qualificada (2/3)'),
    ]

    titulo = models.CharField(max_length=200)
    descricao = models.TextField()
    data = models.DateField()
    hora = models.TimeField()
    autor = models.ForeignKey("Vereador", on_delete=models.CASCADE)
    tipo = models.CharField(max_length=100)
    sessao = models.ForeignKey("Sessao", on_delete=models.CASCADE)
    origem = models.CharField(max_length=20, choices=ORIGEM_CHOICES)
    arquivo_pdf = models.FileField(upload_to="pautas_pdfs/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Em Espera")
    
    votacao_aberta = models.BooleanField(default=True)
    tipo_votacao = models.CharField(max_length=20, choices=TIPOS_VOTACAO, default='simples')

    def __str__(self):
        return f"{self.titulo} - {self.status}"

    def calcular_quorum(self):
        """
        Retorna o número mínimo de votos necessários para aprovação da pauta,
        baseado no tipo de votação.
        """
        total_vereadores = Vereador.objects.count()
        vereadores_presentes = self.sessao.vereadores_presentes.count()

        if self.tipo_votacao == "simples":
            return (vereadores_presentes // 2) + 1  # Maioria dos presentes
        elif self.tipo_votacao == "absoluta":
            return (total_vereadores // 2) + 1  # Maioria absoluta
        elif self.tipo_votacao == "qualificada":
            return (total_vereadores * 2) // 3  # 2/3 dos vereadores

        return 0

    def definir_resultado(self):
        """
        Define automaticamente o resultado da votação com base nos votos e no quórum necessário.
        """
        votos_sim = self.votacao_set.filter(voto="Sim").count()
        votos_nao = self.votacao_set.filter(voto="Não").count()
        total_votos = votos_sim + votos_nao + self.votacao_set.filter(voto="Abstenção").count()

        quorum_minimo = self.calcular_quorum()

        print(f"DEBUG: Votos Sim: {votos_sim}, Votos Não: {votos_nao}, Total Votos: {total_votos}, Quórum Mínimo: {quorum_minimo}")

        if votos_sim >= quorum_minimo:
            self.status = "Aprovada"
        elif votos_sim < quorum_minimo:  # Se os votos "Sim" não atingiram o quórum, a pauta deve ser rejeitada.
            self.status = "Rejeitada"
        else:
            print("DEBUG: Votação ainda em andamento, não atingiu quórum mínimo.")
            return  # Se não atingiu o quórum, continua "Em Votação"

        self.save(update_fields=['status'])  # Salva a mudança no status da pauta

    def pode_iniciar_votacao(self):
        """
        Verifica se há quórum mínimo para iniciar a votação.
        """
        return self.sessao.vereadores_presentes.count() >= ((Vereador.objects.count() // 2) + 1)





# Modelos de Votação
from django.utils import timezone

class Votacao(models.Model):
    VOTO_CHOICES = [
        ('Sim', 'Sim'),
        ('Não', 'Não'),
        ('Abstenção', 'Abstenção')
    ]

    vereador = models.ForeignKey(Vereador, on_delete=models.CASCADE)
    pauta = models.ForeignKey(Pauta, on_delete=models.CASCADE, null=True, blank=True)  
    voto = models.CharField(max_length=10, choices=VOTO_CHOICES, null=True, blank=True)
    presenca = models.BooleanField(default=False)  
    data_hora = models.DateTimeField(default=timezone.now)  # ✅ Define um valor padrão

    class Meta:
        unique_together = ('vereador', 'pauta')

    def __str__(self):
        if self.pauta:
            return f"{self.vereador.nome} - {self.pauta.titulo} - {self.voto if self.voto else 'Sem voto'}"
        return f"{self.vereador.nome} - Presença Registrada"


# Modelos de Relatório
class Relatorio(models.Model):
    sessao = models.ForeignKey(Sessao, on_delete=models.CASCADE)
    data_geracao = models.DateTimeField(auto_now_add=True)
    arquivo = models.FileField(upload_to='relatorios/')

    def __str__(self):
        return f'Relatório da Sessão {self.sessao.nome}'


# Modelos de Cronômetro de Fala
class Cronometro(models.Model):
    vereador = models.ForeignKey(Vereador, on_delete=models.CASCADE)
    tempo_inicial = models.IntegerField()  # Em segundos
    tempo_restante = models.IntegerField()
    status = models.CharField(max_length=10, choices=[('Iniciado', 'Iniciado'), ('Pausado', 'Pausado'), ('Finalizado', 'Finalizado')])
    data_inicio = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Cronômetro - {self.vereador.nome}'

class PresencaRegistrada(models.Model):
    sessao = models.ForeignKey('Sessao', on_delete=models.CASCADE)
    vereador = models.ForeignKey('Vereador', on_delete=models.CASCADE)
    data_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.vereador.nome} - {self.sessao.nome}"


