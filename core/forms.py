from django import forms
from .models import Pauta

class PautaForm(forms.ModelForm):
    class Meta:
        model = Pauta
        fields = ['titulo', 'descricao', 'data', 'hora', 'autor', 'tipo', 'sessao', 'origem', 'arquivo_pdf']
