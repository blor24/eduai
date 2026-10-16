#!/usr/bin/env python3
"""Pruebas observacionales de EduAI. No modifica documentos, índices ni BD.

Subcomandos:
  ollama: API /api/generate; tiempos, tokens y errores, con precalentamiento separado.
  retrieval: RAG vectorial con etiquetas archivo esperado (Hit@k y MRR@k).
  generation: generador real de preguntas + validez estructural (no exactitud pedagógica).
  web: GET sin autenticación de páginas públicas; concurrencia limitada.

Salidas JSON, CSV y MD. No se guardan prompts ni textos de documentos.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import csv
import datetime as dt
import json
import os
from pathlib import Path
import statistics
import sys
import time
import traceback


def load_json(path):
    with open(path, encoding='utf-8') as file:
        return json.load(file)


def percentile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    n = (len(ordered) - 1) * (q / 100)
    lo, hi = int(n), min(int(n) + 1, len(ordered)-1)
    return round(ordered[lo] + (ordered[hi] - ordered[lo]) * (n-lo), 4)


def ns_to_s(value):
    return round(value / 1_000_000_000, 4) if isinstance(value, (float, int)) else None


def trimmed_error(exc):
    return f'{type(exc).__name__}: {str(exc)[:350]}'


def times_summary(rows, key='wall_s'):
    values = [r[key] for r in rows if r.get('ok') and isinstance(r.get(key), (int, float))]
    return {'n': len(values), 'p50_s': percentile(values, 50), 'p95_s': percentile(values, 95),
            'average_s': round(statistics.mean(values), 4) if values else None}


def run_ollama(args):
    import requests
    prompts = load_json(args.prompts)
    if not isinstance(prompts, list) or not prompts:
        raise ValueError('El archivo de prompts debe ser una lista JSON no vacía')
    models = [m.strip() for m in args.models.split(',') if m.strip()]
    if not models:
        raise ValueError('Se requiere al menos un modelo')
    rows = []
    base = os.environ.get('OLLAMA_HOST', 'http://ollama:11434').rstrip('/')
    url = base + '/api/generate'
    for model in models:
        for case in prompts:
            if not isinstance(case, dict) or not case.get('prompt'):
                raise ValueError('Cada caso necesita prompt e idealmente id')
            case_id = str(case.get('id', 'caso'))
            # Precalentamiento se registra separadamente: así se distingue carga en frío.
            for iteration in range(args.repetitions + 1):
                stage = 'warmup' if iteration == 0 else 'measure'
                row = {'test': 'ollama', 'model': model, 'case_id': case_id,
                       'stage': stage, 'iteration': iteration, 'ok': False}
                payload = {'model': model, 'prompt': case['prompt'], 'stream': False,
                           'options': {'num_ctx': args.num_ctx,
                                       'num_predict': args.num_predict,
                                       'temperature': 0.1, 'seed': 42},
                           'keep_alive': '5m'}
                if args.think != 'default':
                    # Ollama controla el razonamiento mediante el campo raíz, no options.
                    payload['think'] = args.think == 'true'
                start = time.perf_counter()
                try:
                    response = requests.post(url, json=payload, timeout=(8, args.timeout))
                    response.raise_for_status()
                    data = response.json()
                    row.update(ok=True, wall_s=round(time.perf_counter() - start, 4),
                               total_s=ns_to_s(data.get('total_duration')),
                               load_s=ns_to_s(data.get('load_duration')),
                               prompt_s=ns_to_s(data.get('prompt_eval_duration')),
                               eval_s=ns_to_s(data.get('eval_duration')),
                               input_tokens=data.get('prompt_eval_count'),
                               output_tokens=data.get('eval_count'))
                    duration = data.get('eval_duration') or 0
                    row['tokens_per_s'] = round((data.get('eval_count') or 0) * 1e9 / duration, 2) if duration else None
                    answer = data.get('response') or ''
                    thinking = data.get('thinking') or ''
                    row['answer_nonempty'] = bool(answer.strip())
                    row['thinking_nonempty'] = bool(thinking.strip())
                    row['answer_chars'] = len(answer)
                    row['thinking_chars'] = len(thinking)
                    row['done_reason'] = data.get('done_reason')
                    row['usable'] = bool(answer.strip())
                    # No se almacenan ni respuestas ni razonamientos, sólo conteos.
                except Exception as exc:
                    row.update(wall_s=round(time.perf_counter() - start, 4), error=trimmed_error(exc))
                rows.append(row)
                print(f"{stage}: {model} / {case_id} / ok={row['ok']} / {row.get('wall_s')}s", flush=True)
    return rows


def run_retrieval(args):
    # Se ejecuta en el backend Docker, con acceso a ChromaDB y la configuración de IA.
    sys.path.insert(0, '/app')
    from vectorstorage import VectorStorageManager
    cases = load_json(args.cases)
    if not isinstance(cases, list) or not cases:
        raise ValueError('El archivo de casos debe ser una lista JSON no vacía')
    vsm = VectorStorageManager()
    rows = []
    retrievers = {}
    for case in cases:
        if not all(case.get(k) for k in ('username', 'query', 'expected_source')):
            raise ValueError('Caso necesita username, query y expected_source')
        key = (case['username'], tuple(case.get('filenames') or ()))
        if key not in retrievers:
            retrievers[key] = vsm.retriever(case['username'], list(key[1]) if key[1] else None)
        retriever = retrievers[key]
        case_id = str(case.get('id', 'caso'))
        for iteration in range(args.repetitions + 1):
            stage = 'warmup' if iteration == 0 else 'measure'
            row = {'test': 'retrieval', 'case_id': case_id, 'stage': stage,
                   'iteration': iteration, 'k': args.k, 'ok': False}
            start = time.perf_counter()
            try:
                # El retriever original usa k=5. Conservamos ese valor por defecto.
                # Se modifica solo este objeto temporal, sin tocar la configuración del servidor.
                retriever.search_kwargs['k'] = args.k
                docs = retriever.invoke(case['query'])
                expected = case['expected_source']
                rank = next((idx for idx, doc in enumerate(docs, start=1)
                             if str(doc.metadata.get('source', '')).replace('\\', '/').rsplit('/', 1)[-1] == expected), None)
                row.update(ok=True, wall_s=round(time.perf_counter() - start, 4),
                           found=rank is not None, rank=rank,
                           reciprocal_rank=round(1/rank, 4) if rank else 0,
                           retrieved_count=len(docs))
            except Exception as exc:
                row.update(wall_s=round(time.perf_counter() - start, 4), error=trimmed_error(exc))
            rows.append(row)
            print(f"{stage}: {case_id}, rank={row.get('rank')}, {row.get('wall_s')}s, ok={row['ok']}", flush=True)
    return rows


def run_generation(args):
    sys.path.insert(0, '/app')
    from llmgeneration import QuestionGenerator
    cases = load_json(args.cases)
    if not isinstance(cases, list) or not cases:
        raise ValueError('El archivo de generación debe ser una lista JSON no vacía')
    rows = []
    models = [s.strip() for s in args.models.split(',') if s.strip()]
    for model in models:
        generator = None
        try:
            generator = QuestionGenerator(ollama_model=model)
        except Exception as exc:
            rows.append({'test': 'generation', 'model': model, 'ok': False, 'error': trimmed_error(exc)})
            continue
        for case in cases:
            for iteration in range(1, args.repetitions + 1):
                row = {'test': 'generation', 'model': model, 'case_id': str(case.get('id', 'caso')),
                       'iteration': iteration, 'ok': False}
                start = time.perf_counter()
                try:
                    result = generator.generate_all_types(case['types'], case['number'], case['username'],
                                                          case['filename'], case.get('difficulty', 'intermedia'))
                    # La implementación real valida la estructura. No se evalúa veracidad factual.
                    count = sum(len(v.get('questions', [])) for v in result.values())
                    row.update(ok=True, wall_s=round(time.perf_counter()-start, 4),
                               question_count=count, types=len(result))
                except Exception as exc:
                    row.update(wall_s=round(time.perf_counter()-start, 4), error=trimmed_error(exc))
                rows.append(row)
                print(f"generation: {model}, {row['case_id']}, ok={row['ok']}, {row.get('wall_s')}s", flush=True)
    return rows


def run_web(args):
    import requests
    from urllib.parse import urlparse
    url = args.url
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        raise ValueError('URL HTTP o HTTPS inválida')
    # Evitar pruebas accidentales a direcciones públicas u otros servidores.
    if parsed.hostname not in ('frontend', 'localhost', '127.0.0.1'):
        raise ValueError('Sólo se permite frontend, localhost o 127.0.0.1')
    if args.method != 'GET':
        raise ValueError('El benchmark web utiliza sólo GET')
    rows = []
    def once(n, concurrencia):
        start = time.perf_counter()
        try:
            response = requests.get(url, timeout=args.timeout, allow_redirects=False)
            status = response.status_code
            return {'test': 'web', 'concurrency': concurrencia, 'iteration': n,
                    'ok': 200 <= status < 400, 'http_status': status,
                    'wall_s': round(time.perf_counter()-start, 4)}
        except Exception as exc:
            return {'test': 'web', 'concurrency': concurrencia, 'iteration': n,
                    'ok': False, 'wall_s': round(time.perf_counter()-start, 4), 'error': trimmed_error(exc)}
    for concurrency in [int(s) for s in args.concurrency.split(',')]:
        if concurrency < 1 or concurrency > 10:
            raise ValueError('Concurrencia permitida entre 1 y 10')
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
            rows.extend(pool.map(lambda i: once(i, concurrency), range(1, args.requests + 1)))
        print(f'web: concurrencia={concurrency}, {args.requests} GET completados', flush=True)
    return rows


def summarize(rows):
    groups = {}
    for row in rows:
        if row.get('stage') == 'warmup':
            continue
        key = str(row.get('model') or row.get('concurrency') or 'global')
        groups.setdefault(key, []).append(row)
    result = {}
    for key, group in groups.items():
        valid = [r for r in group if r.get('ok')]
        metrics = {'runs': len(group), 'success': len(valid), 'errors': len(group)-len(valid)}
        metrics.update(times_summary(valid))
        if any(r.get('test') == 'retrieval' for r in group):
            metrics['hit_at_k'] = round(sum(bool(r.get('found')) for r in valid)/len(valid), 4) if valid else None
            metrics['mrr_at_k'] = round(statistics.mean([r.get('reciprocal_rank', 0) for r in valid]), 4) if valid else None
        if any(r.get('test') == 'ollama' for r in group):
            useful = [r for r in valid if r.get('answer_nonempty')]
            metrics['responses_nonempty'] = len(useful)
            metrics['responses_empty'] = len(valid) - len(useful)
            metrics['thinking_only'] = sum(bool(r.get('thinking_nonempty')) and not r.get('answer_nonempty') for r in valid)
            metrics['p50_usable_s'] = percentile([r['wall_s'] for r in useful if isinstance(r.get('wall_s'), (int,float))], 50)
            metrics['avg_answer_chars'] = round(statistics.mean([r.get('answer_chars', 0) for r in useful]), 1) if useful else 0
        if any('tokens_per_s' in r for r in valid):
            values = [r['tokens_per_s'] for r in valid if isinstance(r.get('tokens_per_s'), (int, float))]
            metrics['tokens_per_s_avg'] = round(statistics.mean(values), 2) if values else None
        result[key] = metrics
    return result


def output_results(rows, args):
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = {'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
            'command': args.action, 'summary': summarize(rows), 'measurements': rows,
            'notes': ['No se incluyen prompts ni respuestas del LLM.',
                      'Los resultados dependen del equipo, índices, prompts y configuración activa.',
                      'Validez del esquema de preguntas no equivale a precisión pedagógica.']}
    with destination.open('w', encoding='utf-8') as out:
        json.dump(data, out, ensure_ascii=False, indent=2)
    csv_path = destination.with_suffix('.csv')
    keys = sorted({key for row in rows for key in row})
    with csv_path.open('w', newline='', encoding='utf-8') as out:
        writer = csv.DictWriter(out, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)
    md_path = destination.with_suffix('.md')
    with md_path.open('w', encoding='utf-8') as out:
        out.write(f'# EduAI: prueba {args.action}\n\nFecha UTC: {data["generated_utc"]}\n\n')
        out.write('Los valores son medidas reales del entorno ejecutado, no estimaciones.\n\n')
        out.write('| Grupo | Éxitos / total | p50 (s) | p95 (s) | Otras métricas |\n|---|---:|---:|---:|---|\n')
        for key, item in data['summary'].items():
            extras = ', '.join(f'{k}: {v}' for k, v in item.items() if k in ('hit_at_k', 'mrr_at_k', 'tokens_per_s_avg', 'responses_nonempty', 'thinking_only', 'p50_usable_s'))
            out.write(f'| {key} | {item["success"]}/{item["runs"]} | {item.get("p50_s")} | {item.get("p95_s")} | {extras} |\n')
    print('\nResumen:')
    print(json.dumps(data['summary'], indent=2, ensure_ascii=False))
    print('\nArchivos:', destination, csv_path, md_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='action', required=True)
    ollama = sub.add_parser('ollama', help='Velocidad del LLM vía API nativa')
    ollama.add_argument('--models', required=True, help='Separados por comas')
    ollama.add_argument('--prompts', required=True)
    ollama.add_argument('--repetitions', type=int, default=2)
    ollama.add_argument('--num-ctx', type=int, default=2048)
    ollama.add_argument('--num-predict', type=int, default=512)
    ollama.add_argument('--think', choices=['default','false','true'], default='default', help='Control de razonamiento Ollama (campo raiz)')
    ollama.add_argument('--timeout', type=int, default=240)
    retrieval = sub.add_parser('retrieval', help='Hit@k, MRR@k y latencia de ChromaDB')
    retrieval.add_argument('--cases', required=True)
    retrieval.add_argument('--k', type=int, default=5)
    retrieval.add_argument('--repetitions', type=int, default=3)
    generation = sub.add_parser('generation', help='Flujo real de generación de preguntas')
    generation.add_argument('--cases', required=True)
    generation.add_argument('--models', required=True)
    generation.add_argument('--repetitions', type=int, default=1)
    web = sub.add_parser('web', help='GET concurrentes a la vista login; sin credenciales')
    web.add_argument('--url', default='http://frontend:8000/admin/login/')
    web.add_argument('--method', choices=['GET'], default='GET')
    web.add_argument('--requests', type=int, default=20)
    web.add_argument('--concurrency', default='1,2,5')
    web.add_argument('--timeout', type=int, default=20)
    for p in (ollama, retrieval, generation, web):
        p.add_argument('--output', required=True, help='Ruta del informe JSON; genera además CSV y Markdown')
    args = parser.parse_args()
    if hasattr(args, 'repetitions') and not (1 <= args.repetitions <= 20):
        parser.error('repetitions debe estar entre 1 y 20')
    if args.action == 'ollama':
        rows = run_ollama(args)
    elif args.action == 'retrieval':
        rows = run_retrieval(args)
    elif args.action == 'generation':
        rows = run_generation(args)
    else:
        if not 1 <= args.requests <= 300:
            parser.error('requests debe estar entre 1 y 300')
        rows = run_web(args)
    output_results(rows, args)
    if not rows or not any(r.get('ok') for r in rows):
        return 2
    if args.action == 'ollama' and not any(r.get('answer_nonempty') for r in rows if r.get('stage') == 'measure'):
        return 3
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print('Error:', trimmed_error(exc), file=sys.stderr)
        sys.exit(1)
