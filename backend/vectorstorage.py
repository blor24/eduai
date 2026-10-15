"""Almacenamiento vectorial versionado y migraciones sin borrar colecciones activas."""
import hashlib
import logging
import os
import fcntl
from contextlib import contextmanager, nullcontext
from pathlib import Path
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from filecontentextractor import FileContentExtractor
from ai_runtime import config, embedding_for

logger = logging.getLogger(__name__)


class VectorStorageManager:
    UPLOAD_FOLDER = 'uploads'
    BASE_DB_FOLDER = 'chroma_dbs'

    def __init__(self):
        Path(self.UPLOAD_FOLDER).mkdir(exist_ok=True)
        Path(self.BASE_DB_FOLDER).mkdir(exist_ok=True)
        self.extractor = FileContentExtractor()
        self.splitter = RecursiveCharacterTextSplitter(chunk_size=1024, chunk_overlap=80)

    @contextmanager
    def lock(self):
        # Serializa modificaciones/reindexación entre procesos backend y worker.
        with open(os.path.join(self.BASE_DB_FOLDER, '.reindex.lock'), 'a+') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def collection_name(username, version):
        if version == 'legacy':
            return f'user_{username}_collection'
        user_hash = hashlib.sha256(username.encode('utf-8')).hexdigest()[:18]
        return f'ed_{user_hash}_{version}'

    def store(self, username, cfg=None, *, version=None):
        cfg = cfg or config()
        return Chroma(collection_name=self.collection_name(username, version or cfg['index_version']),
                      embedding_function=embedding_for(cfg['embedding_provider'], cfg['embedding_model']),
                      persist_directory=self.BASE_DB_FOLDER)

    def insert_collection(self, file_path, username, already_locked=False):
        with (nullcontext() if already_locked else self.lock()):
            cfg = config(force=True)
            text = self.extractor.get_text(file_path)
            if not text or not text.strip():
                raise ValueError('El archivo no contiene texto indexable.')
            src = f'uploads/{username}/{Path(file_path).name}'
            docs = self.splitter.split_documents([Document(page_content=text, metadata={'source': src})])
            if not docs:
                raise ValueError('No se generaron fragmentos del archivo.')
            self.store(username, cfg).add_documents(docs)
            logger.info('Insertados %d fragmentos para %s', len(docs), src)
            return len(docs)

    def delete_collection(self, username, filename, already_locked=False):
        import chromadb
        with (nullcontext() if already_locked else self.lock()):
            # Borra también de versiones históricas: evita recuperar documentos eliminados.
            client = chromadb.PersistentClient(path=self.BASE_DB_FOLDER)
            legacy = self.collection_name(username, 'legacy')
            user_hash = hashlib.sha256(username.encode('utf-8')).hexdigest()[:18]
            prefix = f'ed_{user_hash}_'
            src = f'uploads/{username}/{filename}'
            total = 0
            for c in client.list_collections():
                name = c.name if hasattr(c, 'name') else c
                if name == legacy or name.startswith(prefix):
                    col = client.get_collection(name)
                    ids = col.get(where={'source': src}, include=[])['ids']
                    if ids:
                        col.delete(ids=ids)
                        total += len(ids)
            return total

    def get_docs(self, username, filename):
        import chromadb
        cfg = config()
        client = chromadb.PersistentClient(path=self.BASE_DB_FOLDER)
        name = self.collection_name(username, cfg['index_version'])
        try:
            col = client.get_collection(name)
        except Exception as exc:
            raise ValueError('No existe el índice activo para este usuario') from exc
        src = f'uploads/{username}/{filename}'
        return col.get(where={'source': src}, include=['documents'])['documents']

    def retriever(self, username):
        return self.store(username).as_retriever(search_kwargs={'k': 5})

    def reindex_everyone(self, provider, model, target_version, on_progress=lambda msg: None, on_activate=lambda count: None):
        """Construye una versión nueva. Sólo Django activa después de éxito global."""
        if not target_version or target_version == 'legacy' or not target_version.isalnum():
            raise ValueError('Versión de índice inválida')
        target_cfg = {'embedding_provider': provider, 'embedding_model': model, 'index_version': target_version}
        root = Path(self.UPLOAD_FOLDER)
        built = []
        activation_attempted = False
        with self.lock():
            try:
                for user_dir in sorted(root.iterdir()):
                    if not user_dir.is_dir() or user_dir.name.startswith('.'):
                        continue
                    username = user_dir.name
                    vs = self.store(username, target_cfg)
                    # Existe sólo para esta migración; asegura no reutilizar índices viejos.
                    if vs.get(limit=1, include=[])['ids']:
                        raise RuntimeError('La colección objetivo ya contiene datos: ' + username)
                    built.append((username, vs))
                    count = 0
                    for file in sorted(user_dir.iterdir()):
                        if not file.is_file() or file.suffix.lower() not in ('.docx', '.fodt', '.md', '.odt', '.pdf', '.pptx', '.txt'):
                            continue
                        text = self.extractor.get_text(str(file))
                        if not text or not text.strip():
                            raise ValueError(f'Archivo sin texto: {username}/{file.name}')
                        src = f'uploads/{username}/{file.name}'
                        docs = self.splitter.split_documents([Document(page_content=text, metadata={'source': src})])
                        if not docs:
                            raise ValueError('No se pudo fragmentar: ' + src)
                        vs.add_documents(docs)
                        count += len(docs)
                        on_progress(f'{username}/{file.name}: {count} fragmentos')
                    if count and len(vs.get(include=[])['ids']) != count:
                        raise RuntimeError('Número de vectores no coincide: ' + username)
                    # Consulta de prueba con el nuevo modelo y colección.
                    if count:
                        vs.similarity_search('documento', k=1)
                # Activación y exclusión de nuevas cargas dentro de la misma región crítica.
                activation_attempted = True
                on_activate(len(built))
                return len(built)
            except Exception:
                # La red puede fallar DESPUÉS de que Django haya activado el índice.
                # Nunca borrar un índice cuya activación pudo haber ocurrido.
                if activation_attempted:
                    logger.error('Activación posiblemente confirmada; no se limpiarán índices.')
                    raise
                for username, vs in built:
                    try:
                        vs._client.delete_collection(self.collection_name(username, target_version))
                    except Exception:
                        logger.exception('No se pudo limpiar versión temporal para %s', username)
                raise
