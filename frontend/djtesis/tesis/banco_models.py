from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from .banco_logic import normalizar_pregunta, contenido_examen


class BancoPregunta(models.Model):
    TIPOS = [('multiple', 'Selección múltiple'), ('corta', 'Respuesta corta'),
             ('espacio', 'Completar'), ('emparejar', 'Emparejamiento')]
    DIFICULTADES = [('basica', 'Básica'), ('intermedia', 'Intermedia'), ('avanzada', 'Avanzada')]
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='preguntas_banco')
    archivo = models.ForeignKey('tesis.Archivo', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='preguntas_banco')
    tipo = models.CharField(max_length=12, choices=TIPOS)
    dificultad = models.CharField(max_length=12, choices=DIFICULTADES, default='intermedia')
    dificultad_solicitada = models.CharField(max_length=12, choices=DIFICULTADES + [('mixta', 'Mixta')], default='intermedia', editable=False)
    tema = models.CharField(max_length=120, blank=True)
    enunciado = models.TextField()
    opciones = models.JSONField(default=list, blank=True)
    respuesta_correcta = models.TextField(blank=True)
    explicacion = models.TextField(blank=True)
    terminos = models.JSONField(default=list, blank=True)
    conceptos = models.JSONField(default=list, blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-creado']
        verbose_name = 'Pregunta del banco'
        verbose_name_plural = 'Preguntas del banco'

    def __str__(self):
        return f'{self.get_tipo_display()}: {self.enunciado[:70]}'

    def clean(self):
        super().clean()
        if self.archivo_id and self.usuario_id and self.archivo.user_id != self.usuario_id:
            raise ValidationError({'archivo': 'El documento no pertenece al usuario.'})
        try:
            normalizar_pregunta(self.tipo, {
                'question': self.enunciado, 'options': self.opciones,
                'correct_answer': self.respuesta_correcta, 'explanation': self.explicacion,
                'terms': self.terminos, 'concepts': self.conceptos,
            })
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    def exportar(self):
        return contenido_examen({
            'tipo': self.tipo, 'enunciado': self.enunciado, 'opciones': self.opciones,
            'respuesta_correcta': self.respuesta_correcta, 'explicacion': self.explicacion,
            'terminos': self.terminos, 'conceptos': self.conceptos,
        })


class ExamenGuardado(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='examenes_guardados')
    titulo = models.CharField(max_length=160)
    descripcion = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    preguntas = models.ManyToManyField(BancoPregunta, through='ExamenGuardadoItem', related_name='examenes')

    class Meta:
        ordering = ['-creado']
        verbose_name = 'Examen guardado'
        verbose_name_plural = 'Exámenes guardados'

    def __str__(self):
        return self.titulo


class ExamenGuardadoItem(models.Model):
    examen = models.ForeignKey(ExamenGuardado, on_delete=models.CASCADE, related_name='items')
    pregunta = models.ForeignKey(BancoPregunta, on_delete=models.SET_NULL, null=True, blank=True)
    posicion = models.PositiveSmallIntegerField()
    tipo = models.CharField(max_length=12, choices=BancoPregunta.TIPOS)
    contenido = models.JSONField()

    class Meta:
        ordering = ['posicion']
        constraints = [models.UniqueConstraint(fields=['examen', 'posicion'], name='eduai_examen_posicion_unica')]

    def __str__(self):
        return f'{self.examen_id} - {self.posicion}'
