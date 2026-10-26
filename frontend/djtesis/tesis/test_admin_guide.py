"""Pruebas de acceso y navegación de la guía del administrador."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AdminGuideTests(TestCase):
    def test_regular_user_cannot_view_guide(self):
        user = get_user_model().objects.create_user(username='alumno_guia', password='demo-password')
        self.client.force_login(user)
        response = self.client.get(reverse('admin_guide'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response['Location'])

    def test_superuser_can_view_guide_and_links(self):
        admin = get_user_model().objects.create_superuser(
            username='admin_guia', email='admin@example.com', password='demo-password'
        )
        self.client.force_login(admin)
        response = self.client.get(reverse('admin_guide'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Guía de uso para administradores')
        self.assertContains(response, reverse('ai_panel'))
        self.assertContains(response, reverse('ollama_admin'))

    def test_staff_can_see_general_guide_without_superuser_panel_links(self):
        user = get_user_model().objects.create_user(username='staff_guia', password='demo-password', is_staff=True)
        self.client.force_login(user)
        response = self.client.get(reverse('admin_guide'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Gestión de usuarios y permisos')
        self.assertNotContains(response, 'Abrir configuración de IA')

    def test_admin_home_links_guide(self):
        admin = get_user_model().objects.create_superuser(
            username='admin_menu', email='adminmenu@example.com', password='demo-password'
        )
        self.client.force_login(admin)
        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('admin_guide'))
