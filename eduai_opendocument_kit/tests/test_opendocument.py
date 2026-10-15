"""Pruebas sin Flask/Django/Ollama; ejecuta: python3 -m unittest discover -s tests -v"""
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT / 'archivos' / 'backend'))
from opendocument_text import extract_odf_text, MIMETYPE  # noqa E402

XML_HEADER = '''<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
 xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0">
  <office:body><office:text>
  <text:h>Biología</text:h>
  <text:p>La <text:span>fotosíntesis</text:span> produce oxígeno.</text:p>
  <text:p>Un espacio:<text:s text:c="3"/>fin<text:tab/>tab</text:p>
  <text:list><text:list-item><text:p>Clorofila</text:p></text:list-item></text:list>
  <table:table><table:table-row>
   <table:table-cell><text:p>Luz</text:p></table:table-cell>
   <table:table-cell><text:p>Energía</text:p></table:table-cell>
  </table:table-row></table:table>
  </office:text></office:body></office:document-content>'''


def make_odt(path, content=XML_HEADER, mime=MIMETYPE):
    with ZipFile(path, 'w') as z:
        z.writestr('mimetype', mime, compress_type=ZIP_STORED)
        z.writestr('content.xml', content, compress_type=ZIP_DEFLATED)


class OdfTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_odt_paragraphs_headings_lists_tables_and_whitespace(self):
        path = self.dir / 'clase.odt'
        make_odt(path)
        value = extract_odf_text(path)
        self.assertIn('Biología', value)
        self.assertIn('La fotosíntesis produce oxígeno.', value)
        self.assertIn('Un espacio:   fin\ttab', value)
        self.assertIn('• Clorofila', value)
        self.assertIn('Luz\tEnergía', value)

    def test_odt_invalid_mime(self):
        path = self.dir / 'mal.odt'
        make_odt(path, mime='application/vnd.oasis.opendocument.spreadsheet')
        with self.assertRaisesRegex(ValueError, 'OpenDocument Text'):
            extract_odf_text(path)

    def test_odt_corrupt_archive(self):
        path = self.dir / 'mal.odt'
        path.write_bytes(b'no es un zip')
        with self.assertRaisesRegex(ValueError, 'No se pudo leer OpenDocument'):
            extract_odf_text(path)

    def test_empty_odt(self):
        path = self.dir / 'vacio.odt'
        make_odt(path, XML_HEADER.replace('<text:h>Biología</text:h>', '').replace('<text:p>La <text:span>fotosíntesis</text:span> produce oxígeno.</text:p>', '')
                 .replace('<text:p>Un espacio:<text:s text:c="3"/>fin<text:tab/>tab</text:p>', '')
                 .replace('<text:list><text:list-item><text:p>Clorofila</text:p></text:list-item></text:list>', '')
                 .replace('<table:table><table:table-row>\n   <table:table-cell><text:p>Luz</text:p></table:table-cell>\n   <table:table-cell><text:p>Energía</text:p></table:table-cell>\n  </table:table-row></table:table>', ''))
        with self.assertRaisesRegex(ValueError, 'no contiene texto'):
            extract_odf_text(path)

    def test_fodt(self):
        path = self.dir / 'clase.fodt'
        content = XML_HEADER.replace('<office:document-content\n', '<office:document\n office:mimetype="application/vnd.oasis.opendocument.text"\n').replace('</office:document-content>', '</office:document>')
        path.write_text(content, encoding='utf-8')
        self.assertIn('fotosíntesis', extract_odf_text(path))

    def test_fodt_invalid_mime(self):
        path = self.dir / 'mal.fodt'
        path.write_text(XML_HEADER, encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Flat OpenDocument'):
            extract_odf_text(path)

    def test_prohibit_xml_entities(self):
        path = self.dir / 'mal.fodt'
        content = XML_HEADER.replace('<office:document-content\n', '<office:document\n office:mimetype="application/vnd.oasis.opendocument.text"\n').replace('</office:document-content>', '</office:document>')
        content = content.replace('La <text:span>', '&fake; La <text:span>')
        content = content.replace('<?xml version="1.0" encoding="UTF-8"?>', '<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE foo [<!ENTITY fake "hola">]>')
        path.write_text(content, encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'No se pudo leer OpenDocument'):
            extract_odf_text(path)

    def test_non_odf_rejected(self):
        path = self.dir / 'archivo.xlsx'
        path.write_bytes(b'123')
        with self.assertRaisesRegex(ValueError, 'no soportada'):
            extract_odf_text(path)

if __name__ == '__main__':
    unittest.main()
