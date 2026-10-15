#!/usr/bin/env python3
"""Instalador incremental de OpenDocument para EduAI. No toca datos ni secretos."""
import ast
import re
import shutil
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent
ROOT = KIT.parent
BACKUP = ROOT / '.eduai_odf_backup'
EXTENSIONS = {'.odt', '.fodt', '.md'}


def read(relative):
    path = ROOT / relative
    if not path.is_file():
        raise RuntimeError(f'No existe {relative}; ejecuta el instalador en la raíz de EduAI.')
    return path.read_text(encoding='utf-8')


def replace_once(data, target, replacement, name):
    if replacement in data and target not in data:
        return data
    if data.count(target) != 1:
        raise RuntimeError(f'El formato de {name} cambió; no se puede modificar con seguridad. Buscar: {target[:80]!r}')
    return data.replace(target, replacement, 1)


def prepare_changes():
    changes = {}

    # 1. Extractor Python utilizado por inserciones y reindexaciones.
    path = 'backend/filecontentextractor.py'
    text = read(path)
    if 'from opendocument_text import extract_odf_text' not in text:
        text = 'from opendocument_text import extract_odf_text\n' + text
    old = '        elif ext == ".txt":\n            return self.read_txt(file_path)'
    new = ('        elif ext in (".txt", ".md"):\n'
           '            return self.read_txt(file_path)\n\n'
           '        elif ext in (".odt", ".fodt"):\n'
           '            return extract_odf_text(file_path)')
    if new not in text:
        text = replace_once(text, old, new, path)
    changes[path] = text

    # 2. Lista permitida y error descriptivo Flask.
    path = 'backend/eduai-backend.py'
    text = read(path)
    match = re.search(r'(?m)^ALLOWED_EXTENSIONS\s*=\s*(\{[^}\n]*\})', text)
    if not match:
        raise RuntimeError('No se encontró ALLOWED_EXTENSIONS en backend/eduai-backend.py')
    try:
        existing = ast.literal_eval(match.group(1))
    except (SyntaxError, ValueError) as error:
        raise RuntimeError('ALLOWED_EXTENSIONS no es un conjunto literal de Python') from error
    if not isinstance(existing, set) or not all(isinstance(e, str) for e in existing):
        raise RuntimeError('ALLOWED_EXTENSIONS no contiene extensiones en formato esperado')
    allowed = existing | EXTENSIONS
    new_set = '{' + ', '.join(repr(v) for v in sorted(allowed)) + '}'
    text = text[:match.start(1)] + new_set + text[match.end(1):]
    message = 'Extensión de archivo no permitido. Solo archivos .pdf, .doc, .docx, y .pptx son aceptados.'
    if message in text:
        text = text.replace("'" + message + "'",
                            "'Extensión no permitida. Admitidos: ' + ', '.join(sorted(ALLOWED_EXTENSIONS))", 1)
    changes[path] = text

    # 3. Worker: incluir los nuevos formatos en reindex_everyone.
    path = 'backend/vectorstorage.py'
    text = read(path)
    matches = list(re.finditer(r'file\.suffix\.lower\(\)\s+not\s+in\s+(\([^\n]*?\))', text))
    if len(matches) != 1:
        raise RuntimeError('No se identificó de manera inequívoca el filtro de archivos del ai_worker en vectorstorage.py')
    target = matches[0].group(1)
    existing = ast.literal_eval(target)
    if not isinstance(existing, tuple) or not all(isinstance(e, str) for e in existing):
        raise RuntimeError('Lista de reindexación no reconocida')
    new = '(' + ', '.join(repr(e) for e in sorted(set(existing) | EXTENSIONS)) + ')'
    text = text[:matches[0].start(1)] + new + text[matches[0].end(1):]
    changes[path] = text

    # 4. El usuario puede ver y seleccionar extensiones admitidas desde HTML.
    path = 'frontend/djtesis/tesis/templates/tesis/archivos.html'
    text = read(path)
    matches = list(re.finditer(r'<input\b[^>]*\bid=["\']formFile["\'][^>]*>', text, re.S))
    if len(matches) != 1:
        raise RuntimeError('No se encontró el campo de archivos formFile de Django')
    original_input = matches[0].group(0)
    updated_input = original_input
    if re.search(r'\baccept\s*=', original_input):
        updated_input = re.sub(r'\baccept\s*=\s*(["\']).*?\1',
                               'accept=".pdf,.docx,.pptx,.txt,.odt,.fodt,.md"', original_input, count=1)
    else:
        updated_input = original_input[:-1] + ' accept=".pdf,.docx,.pptx,.txt,.odt,.fodt,.md">'
    hint = ('\n      <div class="form-text">Admitidos: PDF, DOCX, PPTX, TXT, '
            'OpenDocument (ODT/FODT) y Markdown (MD).</div>')
    if 'OpenDocument (ODT/FODT)' not in text:
        updated_input += hint
    text = text[:matches[0].start()] + updated_input + text[matches[0].end():]
    changes[path] = text

    # 5. Añadir dependencia explícita, evitando depender de una transitiva.
    path = 'backend/requirements.docker.txt'
    text = read(path)
    if not re.search(r'(?m)^defusedxml(?:[<=>~!]|\s|$)', text, re.I):
        text = text.rstrip() + '\ndefusedxml==0.7.1\n'
    changes[path] = text

    # 6. El directorio de respaldo no debe aparecer al ejecutar git add .
    path = '.gitignore'
    ignore_file = ROOT / path
    ignored = ignore_file.read_text(encoding='utf-8') if ignore_file.exists() else ''
    if '.eduai_odf_backup/' not in ignored.splitlines():
        ignored = ignored.rstrip() + '\n.eduai_odf_backup/\n'
    changes[path] = ignored

    new_rel = 'backend/opendocument_text.py'
    if (ROOT / new_rel).exists():
        existing = read(new_rel)
        desired = (KIT / 'archivos' / new_rel).read_text(encoding='utf-8')
        if existing != desired:
            raise RuntimeError('backend/opendocument_text.py ya existe y tiene cambios propios; no sobrescribiré.')
    else:
        changes[new_rel] = (KIT / 'archivos' / new_rel).read_text(encoding='utf-8')
    return changes


def main():
    changes = prepare_changes()  # Todas las precondiciones antes de cualquier escritura.
    for path, text in changes.items():
        compile(text, path, 'exec') if path.endswith('.py') else None
    for relative, text in changes.items():
        file_path = ROOT / relative
        if file_path.exists() and file_path.read_text(encoding='utf-8') == text:
            continue
        if file_path.exists():
            backup = BACKUP / relative
            backup.parent.mkdir(parents=True, exist_ok=True)
            if not backup.exists():
                shutil.copy2(file_path, backup)
        else:
            file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(text, encoding='utf-8')
        print('Actualizado:', relative)
    print('Instalación preparada. Ejecuta git diff y docker compose up -d --build backend ai_worker frontend.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, SyntaxError, ValueError) as error:
        sys.exit('ERROR: ' + str(error))
