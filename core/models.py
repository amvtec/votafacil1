from django.db import models
from cloudinary.models import CloudinaryField
from django.utils import timezone
from django.core.validators import RegexValidator

class Vereador(models.Model):
    nome = models.CharField(max_length=100)
    apelido = models.CharField(max_length=100)
    cpf = models.CharField(max_length=11)
    email = models.EmailField()
    telefone = models.CharField(max_length=15)
    partido = models.CharField(max_length=50)
    senha = models.CharField(max_length=100)
    foto = CloudinaryField('image', folder='fotos_vereadores/')
    funcao = models.CharField(max_length=50, choices=[
        ('Vereador', 'Vereador'),
        ('Presidente', 'Presidente'),
        ('Vice-Presidente', 'Vice-Presidente'),
        ('Primeiro Secretário', 'Primeiro Secretário')
    ])
    status = models.CharField(max_length=10, choices=[
        ('Ativo', 'Ativo'),
        ('Inativo', 'Inativo')
    ])

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Vereador"
        verbose_name_plural = "Vereadores"


class Sessao(models.Model):
    nome = models.CharField(max_length=100)
    data = models.DateField()
    hora = models.TimeField()
    arquivada = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=[('Em Andamento', 'Em Andamento'), ('Arquivada', 'Arquivada')]
    )
    vereadores_presentes = models.ManyToManyField("Vereador", blank=True)
    encerrada_em = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Sessão"
        verbose_name_plural = "Sessões"


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
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.titulo} - {self.status}"

    def calcular_quorum(self):
        total_vereadores = Vereador.objects.count()
        vereadores_presentes = self.sessao.vereadores_presentes.count()

        if self.tipo_votacao == "simples":
            return (vereadores_presentes // 2) + 1
        elif self.tipo_votacao == "absoluta":
            return (total_vereadores // 2) + 1
        elif self.tipo_votacao == "qualificada":
            return (total_vereadores * 2) // 3

        return 0

    def definir_resultado(self):
        votos_sim = self.votacao_set.filter(voto="Sim").count()
        votos_nao = self.votacao_set.filter(voto="Não").count()
        total_votos = votos_sim + votos_nao + self.votacao_set.filter(voto="Abstenção").count()

        quorum_minimo = self.calcular_quorum()

        if votos_sim >= quorum_minimo:
            self.status = "Aprovada"
        elif votos_sim < quorum_minimo:
            self.status = "Rejeitada"
        self.save(update_fields=['status'])

    def pode_iniciar_votacao(self):
        return self.sessao.vereadores_presentes.count() >= ((Vereador.objects.count() // 2) + 1)

    class Meta:
        verbose_name = "Pauta"
        verbose_name_plural = "Pautas"


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
    data_hora = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('vereador', 'pauta')
        verbose_name = "Votação"
        verbose_name_plural = "Votações"

    def __str__(self):
        if self.pauta:
            return f"{self.vereador.nome} - {self.pauta.titulo} - {self.voto if self.voto else 'Sem voto'}"
        return f"{self.vereador.nome} - Presença Registrada"


class Relatorio(models.Model):
    sessao = models.ForeignKey(Sessao, on_delete=models.CASCADE)
    data_geracao = models.DateTimeField(auto_now_add=True)
    arquivo = models.FileField(upload_to='relatorios/')

    def __str__(self):
        return f'Relatório da Sessão {self.sessao.nome}'

    class Meta:
        verbose_name = "Relatório"
        verbose_name_plural = "Relatórios"


class Cronometro(models.Model):
    vereador = models.ForeignKey(Vereador, on_delete=models.CASCADE)
    tempo_inicial = models.IntegerField()
    tempo_restante = models.IntegerField()
    tempo_extra = models.IntegerField(default=0)
    status = models.CharField(max_length=10, choices=[('Iniciado', 'Iniciado'), ('Pausado', 'Pausado'), ('Finalizado', 'Finalizado')])
    data_inicio = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Cronômetro - {self.vereador.nome}'

    class Meta:
        verbose_name = "Cronômetro"
        verbose_name_plural = "Cronômetros"


class PresencaRegistrada(models.Model):
    sessao = models.ForeignKey('Sessao', on_delete=models.CASCADE)
    vereador = models.ForeignKey('Vereador', on_delete=models.CASCADE)
    data_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.vereador.nome} - {self.sessao.nome}"

    class Meta:
        verbose_name = "Presença Registrada"
        verbose_name_plural = "Presenças Registradas"


class CamaraMunicipal(models.Model):
    nome = models.CharField(max_length=255)
    cnpj = models.CharField(
        max_length=18,
        blank=True,
        null=True,
        validators=[
            RegexValidator(
                regex=r'^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$',
                message="O CNPJ deve estar no formato 00.000.000/0000-00"
            )
        ]
    )
    endereco = models.CharField(max_length=255, blank=True, null=True)
    numero = models.CharField(max_length=10, blank=True, null=True)
    cidade = models.CharField(max_length=100, blank=True, null=True)
    uf = models.CharField(max_length=2, blank=True, null=True)
    papel_de_parede = CloudinaryField('Imagem de fundo', blank=True, null=True)
    logo = CloudinaryField('Logo da Câmara', blank=True, null=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Câmara Municipal"
        verbose_name_plural = "Câmaras Municipais"


class Live(models.Model):
    nome = models.CharField(max_length=255)
    link = models.URLField()

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Live"
        verbose_name_plural = "Lives"