from django import forms
from django.core.exceptions import ValidationError
from .banco_models import BancoPregunta
from .models import Archivo
from .banco_logic import normalizar_pregunta


class BancoPreguntaForm(forms.ModelForm):
    opciones_texto = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 4}),
                                    label='Opciones (una por línea; solo múltiple)')
    terminos_texto = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 4}),
                                    label='Términos (uno por línea; solo emparejar)')
    conceptos_texto = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 4}),
                                     label='Conceptos correspondientes en el mismo orden')

    class Meta:
        model = BancoPregunta
        fields = ['archivo', 'tipo', 'dificultad', 'tema', 'enunciado',
                  'respuesta_correcta', 'explicacion']
        widgets = {'enunciado': forms.Textarea(attrs={'rows': 3}),
                   'explicacion': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        self.fields['archivo'].queryset = Archivo.objects.filter(user=usuario) if usuario else Archivo.objects.none()
        if self.instance.pk:
            self.fields['opciones_texto'].initial = '\n'.join(self.instance.opciones or [])
            self.fields['terminos_texto'].initial = '\n'.join(self.instance.terminos or [])
            self.fields['conceptos_texto'].initial = '\n'.join(self.instance.conceptos or [])
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control' if not isinstance(field.widget, forms.Select) else 'form-select'

    def clean(self):
        data = super().clean()
        if self.errors:
            return data
        tipo = data['tipo']
        def lines(key):
            return [x.strip() for x in data.get(key, '').splitlines() if x.strip()]
        options = lines('opciones_texto') if tipo == 'multiple' else []
        terms = lines('terminos_texto') if tipo == 'emparejar' else []
        concepts = lines('conceptos_texto') if tipo == 'emparejar' else []
        try:
            fields = normalizar_pregunta(tipo, {
                'question': data['enunciado'], 'correct_answer': data.get('respuesta_correcta', ''),
                'explanation': data.get('explicacion', ''),
                'options': options, 'terms': terms, 'concepts': concepts,
            })
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        self._campos_normalizados = fields
        self.instance.opciones = fields['opciones']
        self.instance.terminos = fields['terminos']
        self.instance.conceptos = fields['conceptos']
        data['respuesta_correcta'] = fields['respuesta_correcta']
        return data

    def save(self, commit=True):
        obj = super().save(commit=False)
        for field in ('opciones', 'respuesta_correcta', 'terminos', 'conceptos'):
            setattr(obj, field, self._campos_normalizados[field])
        if self.usuario:
            obj.usuario = self.usuario
        if commit:
            obj.full_clean()
            obj.save()
        return obj
