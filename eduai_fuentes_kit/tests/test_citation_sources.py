import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'archivos' / 'backend'))
from citation_sources import make_context, finalize_references


class SourcesTest(unittest.TestCase):
    @staticmethod
    def doc(source, text, **metadata):
        return SimpleNamespace(page_content=text, metadata={'source': source, **metadata})

    def test_source_filter_and_pdf_page(self):
        docs = [
            self.doc('uploads/ana/biologia.pdf', 'Energía solar', page=3),
            self.doc('uploads/ana/no_seleccionado.pdf', 'No se debe ver', page=2),
            self.doc('uploads/juan/privado.pdf', 'Otro usuario', page=1),
            self.doc('uploads/ana/notas.odt', 'La clorofila absorbe luz'),
        ]
        context, sources = make_context(docs, username='ana', filenames=['biologia.pdf', 'notas.odt'])
        self.assertEqual(len(sources), 2)
        self.assertEqual(sources[0]['page'], 3)
        self.assertIsNone(sources[1]['page'])
        self.assertNotIn('Otro usuario', context)
        self.assertNotIn('No se debe ver', context)
        self.assertIn('[1]', context)
        self.assertIn('[2]', context)

    def test_invalid_page_never_invented(self):
        docs = [self.doc('uploads/ana/f.pdf', 'Texto', page='unknown')]
        _, sources = make_context(docs, username='ana', filenames=['f.pdf'])
        self.assertIsNone(sources[0]['page'])

    def test_invalid_citations_are_removed(self):
        docs = [self.doc('uploads/ana/f.pdf', 'Texto')]
        _, sources = make_context(docs, username='ana', filenames=['f.pdf'])
        result, sources = finalize_references('Correcto [1] falso [9]', sources)
        self.assertEqual(result, 'Correcto [1] falso ')
        self.assertTrue(sources[0]['cited'])

    def test_no_sources_when_retriever_empty(self):
        context, sources = make_context([], username='ana', filenames=['f.pdf'])
        self.assertEqual(context, '')
        self.assertEqual(sources, [])

    def test_long_context_and_excerpt_capped(self):
        docs = [self.doc('uploads/ana/f.txt', 'A' * 8000)]
        context, sources = make_context(docs, username='ana', filenames=['f.txt'])
        self.assertLess(len(context), 3100)
        self.assertEqual(len(sources[0]['excerpt']), 320)

    def test_malicious_path_is_rejected(self):
        docs = [self.doc('uploads/ana/../juan/secret.pdf', 'Privado')]
        _, sources = make_context(docs, username='ana', filenames=['../juan/secret.pdf'])
        self.assertFalse(sources)


if __name__ == '__main__':
    unittest.main()
