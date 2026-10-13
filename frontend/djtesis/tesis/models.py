from django.db import models
from django.contrib.auth.models import User

class Archivo(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    nombre = models.CharField(max_length=255)
    tipo = models.CharField(max_length=5, null=True, blank=True)
    fecha_carga = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre

class Estadistica(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    tiempo_estudio = models.FloatField(null=True, blank=True)
    puntaje = models.IntegerField(null=True, blank=True)
    momento_uso = models.DateTimeField(auto_now_add=True)
    tiempo_chat = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username if self.user else 'Unknown User'} - {self.puntaje}"

class Mensaje(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    receiver = models.TextField(null=True)
    sender_content = models.TextField()
    receiver_response = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Mensaje de {self.sender.username} a {self.receiver or 'asistente'}"
