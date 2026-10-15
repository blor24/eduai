"""Servicio de trabajos en segundo plano; inicia con `python ai_worker.py`."""
import logging
import os
import time
from statistics import mean
import requests
from ai_runtime import TOKEN, CONFIG_URL, embedding_for
from vectorstorage import VectorStorageManager
from ai_runtime import config

logging.basicConfig(level=logging.INFO)
log = logging.getLogger('eduai.ai_worker')
BASE = os.getenv('DJANGO_BASE_URL', 'http://frontend:8000').rstrip('/')
HEADERS = {'X-EduAI-Internal-Token': TOKEN}


def post(path, body=None):
    r = requests.post(BASE + path, json=body or {}, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()


def report(job, status, progress='', error=''):
    return post(f"/internal/ai/jobs/{job['id']}/report/",
                {'status': status, 'progress': progress, 'error': error})


def execute(job):
    name, provider, kind = job['model_name'], job['provider'], job['kind']
    if kind == 'benchmark':
        r = requests.get(BASE + '/internal/ai/tests/', headers=HEADERS, timeout=20)
        r.raise_for_status()
        cases = r.json()['cases']
        if not cases:
            raise ValueError('Registra al menos un caso de prueba en Django Admin')
        vsm = VectorStorageManager()
        rr, elapsed = [], []
        for case in cases:
            t0 = time.perf_counter()
            docs = vsm.store(case['username']).similarity_search(case['query'], k=5)
            elapsed.append(time.perf_counter() - t0)
            rank = next((i for i, d in enumerate(docs, 1)
                         if d.metadata.get('source', '').endswith('/' + case['expected_filename'])), None)
            rr.append(1 / rank if rank else 0.0)
        return f"n={len(cases)} | Hit@5={sum(v > 0 for v in rr)/len(rr):.3f} | MRR@5={mean(rr):.3f} | latencia={mean(elapsed):.3f}s"
    if kind == 'download':
        if provider != 'hf':
            raise ValueError('Descarga permitida sólo para HF')
        embedding_for('hf', name).embed_query('prueba de instalación')
        return 'Modelo Hugging Face instalado y probado'
    if kind == 'delete':
        if provider != 'hf':
            raise ValueError('Eliminación permitida sólo para HF')
        active = config()
        if active['embedding_provider'] == provider and active['embedding_model'] == name:
            raise ValueError('No se puede eliminar el embedding activo')
        from huggingface_hub import scan_cache_dir
        hf_home = os.getenv('HF_HOME', '/app/.cache/huggingface')
        path = os.path.join(hf_home, 'hub')
        info = scan_cache_dir(path)
        revisions = [rev.commit_hash for repo in info.repos if repo.repo_id == name
                     for rev in repo.revisions]
        if revisions:
            info.delete_revisions(*revisions).execute()
        embedding_for.cache_clear()
        return 'Caché eliminado' if revisions else 'El modelo no estaba en caché'
    if kind == 'reindex':
        emb = embedding_for(provider, name)
        emb.embed_query('prueba de compatibilidad')
        vs = VectorStorageManager()
        def progress(msg):
            report(job, 'progress', msg)
        def activate(count):
            report(job, 'success', f'Índice validado y activo para {count} usuarios')
        count = vs.reindex_everyone(provider, name, job['target_version'], progress, activate)
        return None
    raise ValueError('Operación no soportada')


def main():
    if not TOKEN:
        raise SystemExit('AI_INTERNAL_TOKEN es obligatorio para ai_worker')
    log.info('Worker de EduAI activo')
    while True:
        try:
            job = post('/internal/ai/jobs/claim/').get('job')
            if job:
                try:
                    result = execute(job)
                    if result is not None:
                        report(job, 'success', result)
                    log.info('Trabajo %s completado: %s', job['id'], result)
                except Exception as exc:
                    log.exception('Trabajo %s falló', job['id'])
                    try:
                        report(job, 'failed', error=str(exc))
                    except Exception:
                        log.exception('Fallo informando resultado')
            else:
                time.sleep(5)
        except (requests.RequestException, ValueError):
            log.exception('No se puede contactar API interna')
            time.sleep(10)


if __name__ == '__main__':
    main()
