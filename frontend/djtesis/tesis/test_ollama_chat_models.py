"""No exponer modelos solo-embedding como opciones de conversación."""
from unittest.mock import patch

import requests
from django.core.cache import cache
from django.test import SimpleTestCase

from .ollama_api import list_chat_models, list_embedding_models, list_models, model_capabilities


class OllamaChatModelsTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @staticmethod
    def response(data):
        from unittest.mock import Mock
        response = Mock()
        response.json.return_value = data
        response.raise_for_status.return_value = None
        return response

    @patch('tesis.ollama_api.requests.post')
    @patch('tesis.ollama_api.requests.get')
    def test_chat_filters_embedding_only_models(self, get, post):
        get.return_value = self.response({'models': [
            {'name': 'gemma3:4b', 'digest': 'gen-v1', 'details': {}},
            {'name': 'embeddinggemma-2:270m', 'digest': 'embed-v1', 'details': {}},
            {'name': 'modelo-multimodal:latest', 'digest': 'multi-v1', 'details': {}},
        ]})

        def show(url, json, timeout):
            capabilities = {
                'gemma3:4b': ['completion'],
                'embeddinggemma-2:270m': ['embedding'],
                'modelo-multimodal:latest': ['completion', 'vision'],
            }
            return self.response({'capabilities': capabilities[json['model']]})

        post.side_effect = show
        available = [m['name'] for m in list_chat_models()]
        self.assertEqual(available, ['gemma3:4b', 'modelo-multimodal:latest'])
        # La administración de Ollama debe seguir viendo TODOS los modelos.
        self.assertEqual(len(list_models()), 3)

        # Evitar un /api/show por usuario en cada refresco del selector.
        list_chat_models()
        self.assertEqual(post.call_count, 3)
        self.assertEqual(get.call_count, 3)

    @patch('tesis.ollama_api.requests.post')
    @patch('tesis.ollama_api.requests.get')
    def test_show_without_capabilities_is_not_assumed_chat(self, get, post):
        get.return_value = self.response({'models': [
            {'name': 'sin-capacidades:latest', 'digest': 'v1', 'details': {}},
        ]})
        post.return_value = self.response({})
        self.assertEqual(list_chat_models(), [])

    @patch('tesis.ollama_api.requests.post')
    @patch('tesis.ollama_api.requests.get')
    def test_show_error_for_one_model_keeps_other_models(self, get, post):
        get.return_value = self.response({'models': [
            {'name': 'emb:latest', 'digest': 'a', 'details': {}},
            {'name': 'gemma3:4b', 'digest': 'b', 'details': {}},
        ]})

        def show(url, json, timeout):
            if json['model'] == 'emb:latest':
                raise requests.Timeout('timeout')
            return self.response({'capabilities': ['completion']})

        post.side_effect = show
        self.assertEqual([m['name'] for m in list_chat_models()], ['gemma3:4b'])

    @patch('tesis.ollama_api.requests.post')
    @patch('tesis.ollama_api.requests.get')
    def test_all_show_errors_raise_service_error(self, get, post):
        get.return_value = self.response({'models': [
            {'name': 'gemma3:4b', 'digest': 'c', 'details': {}},
        ]})
        post.side_effect = requests.Timeout('timeout')
        with self.assertRaises(requests.RequestException):
            list_chat_models()

    def test_invalid_name_is_rejected_before_network_request(self):
        with self.assertRaises(ValueError):
            model_capabilities('../../wrong')


class EmbeddingModelDiscoveryTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @staticmethod
    def response(data):
        from unittest.mock import Mock
        response = Mock()
        response.json.return_value = data
        response.raise_for_status.return_value = None
        return response

    @patch('tesis.ollama_api.requests.post')
    @patch('tesis.ollama_api.requests.get')
    def test_only_installed_embedding_capable_models_are_offered(self, get, post):
        get.return_value = self.response({'models': [
            {'name': 'gemma3:4b', 'digest': 'gen-v1'},
            {'name': 'embeddinggemma-2:270m', 'digest': 'embed-v1'},
            {'name': 'modelo-mixto:latest', 'digest': 'mix-v1'},
        ]})
        caps = {
            'gemma3:4b': ['completion'],
            'embeddinggemma-2:270m': ['embedding'],
            'modelo-mixto:latest': ['completion', 'embedding'],
        }
        post.side_effect = lambda url, json, timeout: self.response({'capabilities': caps[json['model']]})
        names = [model['name'] for model in list_embedding_models()]
        self.assertEqual(names, ['embeddinggemma-2:270m', 'modelo-mixto:latest'])
        list_chat_models()
        self.assertEqual(post.call_count, 3)

    @patch('tesis.ai_control.list_embedding_models')
    def test_validation_rejects_non_installed_ollama_model(self, discovered):
        from .ai_control import _allowed
        discovered.return_value = [{'name': 'embeddinggemma-2:270m'}]
        self.assertTrue(_allowed('ollama', 'embeddinggemma-2:270m'))
        self.assertFalse(_allowed('ollama', 'embeddinggemma'))
        self.assertFalse(_allowed('ollama', 'gemma3:4b'))
        self.assertTrue(_allowed('hf', 'sentence-transformers/all-MiniLM-L12-v2'))
        self.assertTrue(_allowed('hf', 'mi-org/mi-embedding'))
        self.assertFalse(_allowed('hf', '../modelo'))
        self.assertFalse(_allowed('random', 'mi-org/mi-embedding'))
