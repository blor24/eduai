"""Verifica la sintaxis de filtros Chroma sin cargar modelos pesados."""
import ast
from pathlib import Path
import unittest

SRC = Path(__file__).resolve().parents[2] / 'backend/vectorstorage.py'


class Store:
    def as_retriever(self, *, search_kwargs):
        return search_kwargs


class Manager:
    def store(self, username):
        self.username = username
        return Store()


class RetrieverFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(SRC.read_text())
        manager_cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'VectorStorageManager')
        retriever = next(n for n in manager_cls.body if isinstance(n, ast.FunctionDef) and n.name == 'retriever')
        isolated = ast.fix_missing_locations(ast.Module(body=[retriever], type_ignores=[]))
        scope = {}
        exec(compile(isolated, str(SRC), 'exec'), scope)
        cls.method = staticmethod(scope['retriever'])

    def test_un_archivo(self):
        result = self.method(Manager(), 'alumno1', ['foto.pdf'])
        self.assertEqual(result['filter'], {'source': 'uploads/alumno1/foto.pdf'})

    def test_dos_archivos(self):
        result = self.method(Manager(), 'alumno1', ['foto.pdf', 'ciencia.odt'])
        self.assertEqual(result['filter'], {'$or': [
            {'source':'uploads/alumno1/foto.pdf'},
            {'source':'uploads/alumno1/ciencia.odt'}]})

    def test_no_permite_vacio(self):
        with self.assertRaises(ValueError):
            self.method(Manager(), 'alumno1', [])

    def test_filtro_sin_repetidos(self):
        result = self.method(Manager(), 'alumno1', ['foto.pdf','foto.pdf'])
        self.assertEqual(result['filter'], {'source':'uploads/alumno1/foto.pdf'})
