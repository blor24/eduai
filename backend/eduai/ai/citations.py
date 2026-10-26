"""Referencias RAG basadas exclusivamente en metadatos de ChromaDB.

Las referencias señalan fragmentos recuperados, no prueban automáticamente
la veracidad de todas las afirmaciones de un modelo generativo.
"""
import re
from pathlib import PurePosixPath

CITATION_PATTERN = re.compile(r'\[(\d{1,3})\]')
MAX_REFERENCES = 5
MAX_CONTEXT_CHARS = 3000
MAX_EXCERPT_CHARS = 320


def _positive(value):
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return number if 1 <= number <= 100000 else None


def make_context(documents, *, username, filenames):
    """Prepara contexto numerado y metadatos seguros para el navegador.

    Se validan una segunda vez las fuentes contra el ámbito seleccionado.
    Las rutas internas no se transmiten al navegador.
    """
    prefix = 'uploads/' + username + '/'
    allowed = set(filenames)
    sections, sources = [], []
    for doc in documents[:MAX_REFERENCES]:
        metadata = doc.metadata or {}
        source = metadata.get('source')
        if not isinstance(source, str) or not source.startswith(prefix):
            continue
        name = source[len(prefix):]
        if not name or name not in allowed or PurePosixPath(name).name != name:
            continue
        content = (doc.page_content or '').strip()
        if not content:
            continue
        citation_id = len(sources) + 1
        page = _positive(metadata.get('page'))
        slide = _positive(metadata.get('slide')) if page is None else None
        header = f'[{citation_id}] Documento: {name}'
        if page is not None:
            header += f' | página {page}'
        elif slide is not None:
            header += f' | diapositiva {slide}'
        sections.append(f'{header}\n{content[:MAX_CONTEXT_CHARS]}')
        sources.append({
            'id': citation_id,
            'filename': name,
            'page': page,
            'slide': slide,
            'excerpt': re.sub(r'\s+', ' ', content)[:MAX_EXCERPT_CHARS],
            'cited': False,
        })
    return '\n\n'.join(sections), sources


def finalize_references(answer, sources):
    """Evita mostrar marcadores de cita a fragmentos inexistentes."""
    allowed = {source['id'] for source in sources}
    cited = {int(num) for num in CITATION_PATTERN.findall(answer)
             if int(num) in allowed}
    cleaned = CITATION_PATTERN.sub(
        lambda found: found.group(0) if int(found.group(1)) in allowed else '',
        answer,
    )
    return cleaned, [{**source, 'cited': source['id'] in cited} for source in sources]
