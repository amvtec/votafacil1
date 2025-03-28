from django import forms
from .models import Pauta, Sessao, Vereador, CamaraMunicipal


class SessaoForm(forms.ModelForm):
    data = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'text',
            'placeholder': 'dd/mm/aaaa'
        }),
        input_formats=['%d/%m/%Y']
    )
    hora = forms.TimeField(
        widget=forms.TimeInput(attrs={
            'type': 'text',
            'placeholder': 'hh:mm'
        }),
        input_formats=['%H:%M']
    )

    class Meta:
        model = Sessao
        fields = '__all__'


class PautaForm(forms.ModelForm):
    data = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'text',
            'placeholder': 'dd/mm/aaaa'
        }),
        input_formats=['%d/%m/%Y']
    )
    hora = forms.TimeField(
        widget=forms.TimeInput(attrs={
            'type': 'text',
            'placeholder': 'hh:mm'
        }),
        input_formats=['%H:%M']
    )

    class Meta:
        model = Pauta
        fields = '__all__'


class VereadorForm(forms.ModelForm):
    senha = forms.CharField(widget=forms.PasswordInput())

    class Meta:
        model = Vereador
        fields = '__all__'


class CamaraMunicipalForm(forms.ModelForm):
    class Meta:
        model = CamaraMunicipal
        fields = '__all__'
