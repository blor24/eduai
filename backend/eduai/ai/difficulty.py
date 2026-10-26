"""Instrucciones pedagógicas para generación; no son etiquetas de calidad validadas."""
from collections import Counter

NIVELES = ('basica', 'intermedia', 'avanzada', 'mixta')

INSTRUCCIONES = {
    'basica': (
        'DIFFICULTY: BASIC. Focus on recall and comprehension of facts explicitly stated '
        'in the passage. Use direct, unambiguous wording. Avoid multi-step reasoning. '
        'Correct answers MUST be supported by the passage.'
    ),
    'intermedia': (
        'DIFFICULTY: INTERMEDIATE. Focus on applying concepts, explaining processes and '
        'relating ideas explicitly supported by the passage. Avoid mere definition recall '
        'when a meaningful application is possible. Do not invent facts.'
    ),
    'avanzada': (
        'DIFFICULTY: ADVANCED. Require analysis, comparison or justified inference '
        'based strictly on the passage. A challenging question must still have a '
        'clear, verifiable correct answer, not require outside knowledge.'
    ),
    'mixta': (
        'DIFFICULTY: MIXED. For a matching exercise include a range of basic, intermediate '
        'and advanced concept relations, all directly supported by the passage.'
    ),
}


def instrucciones(nivel):
    if nivel not in NIVELES:
        raise ValueError('Dificultad no permitida.')
    return INSTRUCCIONES[nivel]


def plan_generacion(tipo, numero, dificultad):
    """Devuelve (nivel, tamaño_lote) sin alterar la cantidad solicitada.

    Emparejamiento es un único ejercicio con N pares, no N preguntas.
    """
    numero = int(numero)
    if not 1 <= numero <= 40:
        raise ValueError('La cantidad debe estar entre 1 y 40.')
    if dificultad not in NIVELES:
        raise ValueError('Dificultad no permitida.')
    if tipo == 'emparejar':
        return [(dificultad, numero)]
    if tipo not in {'multiple', 'corta', 'espacio'}:
        raise ValueError('Tipo de pregunta desconocido.')
    if dificultad != 'mixta':
        return [(dificultad, min(4, numero-i)) for i in range(0, numero, 4)]
    counts = Counter(('basica', 'intermedia', 'avanzada')[i % 3] for i in range(numero))
    result = []
    for level in ('basica', 'intermedia', 'avanzada'):
        amount = counts[level]
        while amount:
            size = min(4, amount)
            result.append((level, size))
            amount -= size
    return result
