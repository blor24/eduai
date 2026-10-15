"""Tests sin dependencias Django/Flask: integridad del token de selección."""
import importlib.util
import os
from pathlib import Path
import re
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def mock_filename(name):
    return re.sub(r'[^A-Za-z0-9_.-]', '', '_'.join(name.split())).strip('._')

# Permite validar criptografía/aislamiento sin instalar Flask en el equipo de CI.
werkzeug = types.ModuleType('werkzeug')
utils = types.ModuleType('werkzeug.utils')
utils.secure_filename = mock_filename
werkzeug.utils = utils
sys.modules.setdefault('werkzeug', werkzeug)
sys.modules.setdefault('werkzeug.utils', utils)


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


signer = load('signer', ROOT / 'archivos/frontend/djtesis/tesis/document_scope.py')
verifier = load('verifier', ROOT / 'archivos/backend/document_scope.py')


class DocumentScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        Path('uploads/alumno1').mkdir(parents=True)
        Path('uploads/alumno2').mkdir(parents=True)
        Path('uploads/alumno1/foto.pdf').write_bytes(b'%PDF-1.4')
        Path('uploads/alumno2/privado.pdf').write_bytes(b'%PDF-1.4')
        self.env = patch.dict(os.environ, {'AI_INTERNAL_TOKEN': 'c' * 50})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        os.chdir(self.old)
        self.tmp.cleanup()

    def test_documentos_seleccionados(self):
        token = signer.make_token('alumno1', ['foto.pdf'], now=100)
        self.assertEqual(verifier.verify(token, now=101), ('alumno1', ['foto.pdf']))

    def test_archivo_ajeno_no_incluido(self):
        token = signer.make_token('alumno1', ['privado.pdf'], now=100)
        self.assertEqual(verifier.verify(token, now=101), ('alumno1', []))

    def test_token_manipulado(self):
        token = signer.make_token('alumno1', ['foto.pdf'], now=100)
        token = token[:-1] + ('A' if token[-1] != 'A' else 'B')
        with self.assertRaises(verifier.InvalidDocumentScope):
            verifier.verify(token, now=101)

    def test_token_expirado(self):
        token = signer.make_token('alumno1', ['foto.pdf'], now=100)
        with self.assertRaises(verifier.InvalidDocumentScope):
            verifier.verify(token, now=100 + 12 * 3600 + 1)

    def test_no_traversal(self):
        token = signer.make_token('alumno1', ['../../privado.pdf'], now=100)
        with self.assertRaises(verifier.InvalidDocumentScope):
            verifier.verify(token, now=101)

    def test_archivo_eliminado(self):
        token = signer.make_token('alumno1', ['foto.pdf'], now=100)
        Path('uploads/alumno1/foto.pdf').unlink()
        self.assertEqual(verifier.verify(token, now=101), ('alumno1', []))

    def test_sin_llave(self):
        token = signer.make_token('alumno1', ['foto.pdf'], now=100)
        with patch.dict(os.environ, {'AI_INTERNAL_TOKEN': ''}):
            with self.assertRaises(verifier.InvalidDocumentScope):
                verifier.verify(token, now=101)


if __name__ == '__main__':
    unittest.main()
