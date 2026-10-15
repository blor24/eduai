"""Benchmark del índice activo: python evaluate_ai.py ejemplos_qa.json.
Formato: [{"username":"usuario", "query":"...", "expected_source":"documento.pdf"}]
Se calcula hit@5, MRR@5 y tiempo de recuperación; no requiere respuestas del LLM.
"""
import json
import sys
import time
from statistics import mean
from vectorstorage import VectorStorageManager


def evaluate(path):
    cases = json.load(open(path, encoding='utf-8'))
    if not isinstance(cases, list) or not cases:
        raise ValueError('Se necesita un array JSON con preguntas etiquetadas')
    vsm = VectorStorageManager()
    scores, times = [], []
    for case in cases:
        if not all(case.get(k) for k in ('username', 'query', 'expected_source')):
            raise ValueError('Caso incompleto; se requiere username, query, expected_source')
        t0 = time.perf_counter()
        matches = vsm.store(case['username']).similarity_search(case['query'], k=5)
        times.append(time.perf_counter() - t0)
        rank = next((i for i, d in enumerate(matches, 1)
                     if d.metadata.get('source', '').endswith('/' + case['expected_source'])), None)
        reciprocal = 1 / rank if rank else 0
        scores.append(reciprocal)
        print(f"{case['query'][:60]}: rank={rank or 'no encontrado'}, rr={reciprocal:.3f}")
    print(json.dumps({'casos': len(cases), 'hit_at_5': sum(x > 0 for x in scores) / len(scores),
                      'mrr_at_5': mean(scores), 'latencia_media_segundos': mean(times)}, indent=2))


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Uso: python evaluate_ai.py casos.json')
    evaluate(sys.argv[1])
