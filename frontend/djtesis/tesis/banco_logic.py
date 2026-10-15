"""Funciones sin dependencias Django para el banco de preguntas EduAI."""
from copy import deepcopy

TIPOS = ('multiple', 'corta', 'espacio', 'emparejar')
MAX_PREGUNTAS = 100


def _texto(value):
    return str(value).strip() if isinstance(value, str) else ''


def normalizar_pregunta(tipo, data):
    """Valida un objeto generado por Flask. Devuelve campos listos para el modelo."""
    if tipo not in TIPOS or not isinstance(data, dict):
        raise ValueError('Tipo o contenido inválido.')
    question = _texto(data.get('question'))
    explanation = _texto(data.get('explanation'))
    if tipo == 'emparejar':
        terms, concepts = data.get('terms', []), data.get('concepts', [])
        if (not isinstance(terms, list) or not isinstance(concepts, list)
                or not (1 <= len(terms) == len(concepts) <= 40)
                or not all(_texto(x) for x in terms + concepts)
                or len(set(terms)) != len(terms) or len(set(concepts)) != len(concepts)):
            raise ValueError('El emparejamiento debe tener entre 1 y 40 pares únicos.')
        return dict(tipo=tipo, enunciado=question or 'Empareja los términos y conceptos.',
                    opciones=[], respuesta_correcta='', explicacion=explanation,
                    terminos=[x.strip() for x in terms], conceptos=[x.strip() for x in concepts])

    answer = _texto(data.get('correct_answer'))
    if not question or not answer:
        raise ValueError('Faltan el enunciado o la respuesta correcta.')
    options = data.get('options', []) if tipo == 'multiple' else []
    if tipo == 'multiple':
        if (not isinstance(options, list) or len(options) != 4
                or any(not _texto(x) for x in options)
                or len(set(options)) != 4 or answer not in options):
            raise ValueError('La selección múltiple requiere cuatro opciones únicas y una respuesta válida.')
    if tipo in ('corta', 'espacio') and len(answer.split()) != 1:
        raise ValueError('La respuesta debe tener una palabra.')
    if tipo == 'espacio' and '___' not in question:
        raise ValueError('La pregunta debe incluir ___.')
    return dict(tipo=tipo, enunciado=question, opciones=deepcopy(options),
                respuesta_correcta=answer, explicacion=explanation, terminos=[], conceptos=[])


def extraer_generadas(payload):
    """Transforma la sesión quiz_questions a preguntas individuales validadas."""
    if not isinstance(payload, dict):
        raise ValueError('La sesión no contiene un examen válido.')
    output = []
    for tipo, grupo in payload.items():
        if tipo not in TIPOS or not isinstance(grupo, dict) or not isinstance(grupo.get('questions'), list):
            raise ValueError('La respuesta del generador contiene un grupo inválido.')
        for item in grupo['questions']:
            output.append(normalizar_pregunta(tipo, item))
            if len(output) > MAX_PREGUNTAS:
                raise ValueError('Se superó el máximo de preguntas permitidas.')
    if not output:
        raise ValueError('El examen no contiene preguntas.')
    return output


def contenido_examen(data):
    """Genera formato compatible con tesis.views.examen (snapshot inmutable)."""
    tipo = data['tipo']
    obj = {
        'question': data['enunciado'],
        'correct_answer': data.get('respuesta_correcta', ''),
        'explanation': data.get('explicacion', ''),
    }
    if tipo == 'multiple':
        obj['options'] = deepcopy(data['opciones'])
    elif tipo == 'emparejar':
        obj['terms'] = deepcopy(data['terminos'])
        obj['concepts'] = deepcopy(data['conceptos'])
    return obj


def armar_examen(items):
    """items iterable (tipo, contenido) que devuelve el JSON que consume el examen existente."""
    grupos = {}
    total = 0
    for tipo, data in items:
        if tipo not in TIPOS:
            raise ValueError('Tipo de pregunta no permitido.')
        # Valida antes de almacenarlo en la sesión (evita JSON arbitrario).
        normalized = normalizar_pregunta(tipo, data)
        # Un snapshot puede contener explicación adicional y queda preservada.
        grupos.setdefault(tipo, {'questions': []})['questions'].append(contenido_examen(normalized))
        total += 1
        if total > MAX_PREGUNTAS:
            raise ValueError('Examen demasiado grande.')
    if not total:
        raise ValueError('No se puede crear un examen vacío.')
    return grupos
