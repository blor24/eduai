"""Extractor de texto para OpenDocument (.odt y .fodt).

Lee contenido XML sin invocar LibreOffice ni ejecutar macros. Preserva párrafos,
encabezados, listas y filas de tablas. No realiza OCR de imágenes incrustadas.
"""
from __future__ import annotations

from pathlib import Path
from zipfile import BadZipFile, ZipFile

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

OFFICE = 'urn:oasis:names:tc:opendocument:xmlns:office:1.0'
TEXT = 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'
TABLE = 'urn:oasis:names:tc:opendocument:xmlns:table:1.0'
MIMETYPE = 'application/vnd.oasis.opendocument.text'
MAX_CONTENT_XML = 25 * 1024 * 1024  # Descomprimido, 25 MiB.
MAX_ZIP_ENTRIES = 5000
MAX_COMPRESSION_RATIO = 400


def _tag(ns: str, name: str) -> str:
    return f'{{{ns}}}{name}'


def _inline(element) -> str:
    """Extrae texto en línea respetando los espacios ODF explícitos."""
    parts = [element.text or '']
    for child in element:
        if child.tag == _tag(TEXT, 's'):
            # Evita atributos manipulados con millones de espacios.
            count = int(child.attrib.get(_tag(TEXT, 'c'), '1'))
            if not 1 <= count <= 1000:
                raise ValueError('Cantidad de espacios ODF no válida')
            parts.append(' ' * count)
        elif child.tag == _tag(TEXT, 'tab'):
            parts.append('\t')
        elif child.tag == _tag(TEXT, 'line-break'):
            parts.append('\n')
        else:
            parts.append(_inline(child))
        parts.append(child.tail or '')
    return ''.join(parts)


def _blocks(element):
    """Recorre los bloques en orden visual aproximado del documento."""
    if element.tag in (_tag(TEXT, 'p'), _tag(TEXT, 'h')):
        line = _inline(element).strip()
        if line:
            yield line
        return

    if element.tag == _tag(TABLE, 'table-row'):
        columns = []
        for cell in element:
            if cell.tag in (_tag(TABLE, 'table-cell'), _tag(TABLE, 'covered-table-cell')):
                columns.append(' '.join(_blocks(cell)).strip())
        row = '\t'.join(columns).strip()
        if row:
            yield row
        return

    if element.tag == _tag(TEXT, 'list-item'):
        items = [line for child in element for line in _blocks(child)]
        for pos, item in enumerate(items):
            yield ('• ' if pos == 0 else '  ') + item
        return

    for child in element:
        yield from _blocks(child)


def _read_limited(handle) -> bytes:
    contents = handle.read(MAX_CONTENT_XML + 1)
    if len(contents) > MAX_CONTENT_XML:
        raise ValueError('Documento OpenDocument demasiado grande para extraer texto')
    return contents


def extract_odf_text(filepath: str | Path) -> str:
    """Devuelve el texto de un archivo .odt o .fodt, o ValueError si no es válido."""
    filepath = Path(filepath)
    extension = filepath.suffix.lower()
    if extension not in ('.odt', '.fodt'):
        raise ValueError(f'Extensión no soportada por OpenDocument: {extension}')

    try:
        if extension == '.odt':
            with ZipFile(filepath) as archive:
                if len(archive.infolist()) > MAX_ZIP_ENTRIES:
                    raise ValueError('Demasiadas entradas en el archivo ODT')
                mime_info = archive.getinfo('mimetype')
                if mime_info.file_size > 128:
                    raise ValueError('Cabecera ODT no válida')
                with archive.open(mime_info) as stream:
                    mimetype = stream.read(129).decode('ascii')
                if mimetype != MIMETYPE:
                    raise ValueError('El archivo no es un documento OpenDocument Text (.odt)')

                info = archive.getinfo('content.xml')
                if info.file_size > MAX_CONTENT_XML:
                    raise ValueError('El contenido XML del ODT es demasiado grande')
                if info.file_size > MAX_COMPRESSION_RATIO * max(1, info.compress_size):
                    raise ValueError('Relación de compresión sospechosa en el ODT')
                with archive.open(info) as stream:
                    xml = _read_limited(stream)
        else:
            with filepath.open('rb') as stream:
                xml = _read_limited(stream)

        root = SafeET.fromstring(xml)
        if extension == '.fodt' and root.get(_tag(OFFICE, 'mimetype')) != MIMETYPE:
            raise ValueError('El archivo no es un documento Flat OpenDocument Text (.fodt)')

        body = root.find(f'.//{_tag(OFFICE, "body")}/{_tag(OFFICE, "text")}')
        if body is None:
            raise ValueError('No se encontró el cuerpo de texto de OpenDocument')
        result = '\n'.join(_blocks(body)).strip()
        if not result:
            raise ValueError('El documento OpenDocument no contiene texto indexable')
        return result
    except (BadZipFile, KeyError, UnicodeError, SafeET.ParseError,
            DefusedXmlException, OSError) as error:
        raise ValueError(f'No se pudo leer OpenDocument: {error}') from error
