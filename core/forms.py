from django import forms
from .models import Pauta, Sessao, Vereador, CamaraMunicipal


class SessaoForm(forms.ModelForm):
    data = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date'
        }),
        input_formats=['%d/%m/%Y', '%Y-%m-%d']  # Adiciona suporte a input do navegador
    )
    hora = forms.TimeField(
        widget=forms.TimeInput(attrs={
            'type': 'time'
        }),
        input_formats=['%H:%M']
    )

    class Meta:
        model = Sessao
        fields = '__all__'


class PautaForm(forms.ModelForm):
    descricao = forms.CharField(
        widget=forms.Textarea(attrs={
            'placeholder': 'Descreva a pauta (mínimo 250 e máximo 300 caracteres)',
            'rows': 4,
            'maxlength': 300,
            'minlength': 250,
        }),
        min_length=250,
        max_length=300,
        label='Descrição'
    )

    data = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        input_formats=['%Y-%m-%d'],
        label='Data'
    )

    hora = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time'}),
        input_formats=['%H:%M'],
        label='Hora'
    )

    class Meta:
        model = Pauta
        fields = '__all__'  # ✅ string final corrigida


class VereadorForm(forms.ModelForm):
    senha = forms.CharField(widget=forms.PasswordInput())

    class Meta:
        model = Vereador
        fields = '__all__'


class CamaraMunicipalForm(forms.ModelForm):
    class Meta:
        model = CamaraMunicipal
        fields = '__all__'
