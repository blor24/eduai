"""API de documentos accesible solo desde Django (AI_INTERNAL_TOKEN)."""
import hmac
import os
from pathlib import Path
from flask import Blueprint, abort, jsonify, request, send_file
from werkzeug.utils import secure_filename
from ai_runtime import config
from vectorstorage import VectorStorageManager

api = Blueprint('eduai_documents', __name__)


def authorized():
    expected = os.getenv('AI_INTERNAL_TOKEN', '')
    supplied = request.headers.get('X-EduAI-Internal-Token', '')
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))


def valid_name(name):
    return isinstance(name, str) and bool(name) and name == secure_filename(name) and len(name) <= 255


@api.route('/internal/documents/status', methods=['POST'])
def status():
    if not authorized():
        abort(403)
    payload = request.get_json(silent=True) or {}
    username, filenames = payload.get('username'), payload.get('filenames')
    username = secure_filename(username) if isinstance(username, str) else ''
    if not valid_name(username) or not isinstance(filenames, list) or len(filenames) > 250 or any(not valid_name(n) for n in filenames):
        return jsonify({'error': 'Argumentos incorrectos'}), 400
    import chromadb
    cfg = config(force=True)
    collection_name = VectorStorageManager.collection_name(username, cfg['index_version'])
    client = chromadb.PersistentClient(path=VectorStorageManager.BASE_DB_FOLDER)
    try:
        collection = client.get_collection(collection_name)
    except Exception:
        collection = None
    root = Path(VectorStorageManager.UPLOAD_FOLDER) / username
    documents = {}
    for name in filenames:
        if not (root / name).is_file():
            documents[name] = {'status': 'missing', 'chunks': 0}
            continue
        count = 0
        if collection is not None:
            count = len(collection.get(where={'source': f'uploads/{username}/{name}'}, include=[])['ids'])
        documents[name] = {'status': 'indexed' if count else 'pending', 'chunks': count}
    return jsonify({'documents': documents, 'index_version': cfg['index_version']})


@api.route('/internal/documents/file', methods=['GET'])
def view_file():
    if not authorized():
        abort(403)
    username, filename = request.args.get('username'), request.args.get('filename')
    username = secure_filename(username) if isinstance(username, str) else ''
    if not valid_name(username) or not valid_name(filename):
        abort(400)
    path = Path(VectorStorageManager.UPLOAD_FOLDER) / username / filename
    if not path.is_file():
        abort(404)
    return send_file(path.resolve(), as_attachment=False)


def register(app):
    app.register_blueprint(api)
