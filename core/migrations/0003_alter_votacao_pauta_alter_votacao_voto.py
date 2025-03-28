# Generated by Django 5.1.6 on 2025-03-12 02:58

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_sessao_vereadores_presentes'),
    ]

    operations = [
        migrations.AlterField(
            model_name='votacao',
            name='pauta',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.pauta'),
        ),
        migrations.AlterField(
            model_name='votacao',
            name='voto',
            field=models.CharField(blank=True, choices=[('Sim', 'Sim'), ('Não', 'Não'), ('Abstenção', 'Abstenção')], max_length=10, null=True),
        ),
    ]
