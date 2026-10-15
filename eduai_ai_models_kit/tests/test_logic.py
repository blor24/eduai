"""Pruebas aisladas sin levantar Django, Flask, Hugging Face ni Ollama.
Ejecutar: python3 -m unittest discover -s eduai_ai_models_kit/tests -v
"""
import ast
import hashlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'archivos' / 'backend'


def extract_method(file_name, class_name, method_name, globals=None):
    tree = ast.parse((ROOT / file_name).read_text(encoding='utf-8'))
    cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == class_name)
    fn = next(x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == method_name)
    fn.decorator_list = []
    module = ast.Module(body=[fn], type_ignores=[])
    ns = globals or {}
    exec(compile(ast.fix_missing_locations(module), str(ROOT/file_name), 'exec'), ns)
    return ns[method_name]


class TestEmbeddingsVersioning(unittest.TestCase):
    def test_original_collection_keeps_name(self):
        f = extract_method('vectorstorage.py', 'VectorStorageManager', 'collection_name', {'hashlib': hashlib})
        self.assertEqual(f('damian', 'legacy'), 'user_damian_collection')

    def test_indexes_are_separate(self):
        f = extract_method('vectorstorage.py', 'VectorStorageManager', 'collection_name', {'hashlib': hashlib})
        self.assertNotEqual(f('damian', 'abc123'), f('damian', 'def456'))
        self.assertNotEqual(f('damian', 'abc123'), f('otro', 'abc123'))


class TestGeneratedQuestionShape(unittest.TestCase):
    def setUp(self):
        self.validate = extract_method('llmgeneration.py', 'QuestionGenerator', 'validate_result')

    def test_valid_multiple(self):
        q = {'questions':[{'question':'¿Qué es?', 'options':['a','b','c','d'],
                           'correct_answer':'c','explanation':'Explicación'}]}
        self.assertEqual(len(self.validate('multiple', q, 1)), 1)

    def test_multiple_rejects_incorrect_answer(self):
        q = {'questions':[{'question':'¿Qué es?', 'options':['a','b','c','d'],
                           'correct_answer':'x','explanation':'Explicación'}]}
        with self.assertRaises(ValueError): self.validate('multiple', q, 1)

    def test_fill_requires_blank(self):
        q = {'questions':[{'question':'Completa', 'correct_answer':'sol','explanation':'Explicación'}]}
        with self.assertRaises(ValueError): self.validate('espacio', q, 1)

    def test_short_one_word(self):
        q = {'questions':[{'question':'¿Qué es?', 'correct_answer':'dos palabras','explanation':'Explicación'}]}
        with self.assertRaises(ValueError): self.validate('corta', q, 1)

    def test_matching_exact_count(self):
        q = {'questions':[{'terms':['a'], 'concepts':['A']}]}
        with self.assertRaises(ValueError): self.validate('emparejar', q, 2)


if __name__ == '__main__': unittest.main()
