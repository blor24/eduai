import eventlet

eventlet.monkey_patch()
from flask import Flask, jsonify, request, send_file, g
from werkzeug.utils import secure_filename
import os
from flask_socketio import SocketIO, emit
import requests
import io, zipfile
from eduai.ai.chat import PDFStorage, RAGApplication, ChooseModel
from eduai.storage.vectors import VectorStorageManager
from eduai.ai.generation import QuestionGenerator, create_questions_pdf, create_questions_docx

from pathlib import Path
from eduai.api.documents import register as register_document_routes
from eduai.api.scope import verify as verify_document_scope, InvalidDocumentScope
#FLASK_cors para permitir comunicacion en el mismo host
#from flask_cors import CORS
### CONFIGURACIONES
app = Flask(__name__)
register_document_routes(app)
DJANGO_BASE_URL = os.environ.get("DJANGO_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

#Permitir peticiones desde el mismo host
#CORS(app, origins=['http://192.168.42.103:8000','http://192.168.42.103'])
#socketio = SocketIO(app, cors_allowed_origins=['http://192.168.42.103:8000','http://192.168.42.103'])

socketio = SocketIO(app, cors_allowed_origins="*")



### SECCION PARA CALCULAR TIEMPOS DE RESPUESTA
import time

LOG_FILE = "tiempos.log"

@app.before_request
def start_timer():
    g.start_time = time.perf_counter()

@app.after_request
def log_request_time(response):
    if hasattr(g, 'start_time'):
        duration = time.perf_counter() - g.start_time
        log_line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {request.method} {request.path} | {duration:.4f} sec\n"
        with open(LOG_FILE, "a") as f:
            f.write(log_line)
    return response
###

UPLOAD_FOLDER = "uploads"
BASE_DB_FOLDER = "chroma_dbs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(BASE_DB_FOLDER, exist_ok=True)

# Extensiones definidas.
ALLOWED_EXTENSIONS = {'.docx', '.fodt', '.md', '.odt', '.pdf', '.pptx', '.txt'}

### METODOS PARA ENDPOINTS
def allowed_file(filename):
    # Chequea si el archivo pertence al grupo de extensiones permitidas.
    ext = os.path.splitext(filename)[1].lower()  # Obtiene la extensión.
    return ext in ALLOWED_EXTENSIONS

### ENDPOINTS
@app.route('/upload', methods=['POST'])
def upload():
    from eduai.api.documents import authorized
    if not authorized():
        return jsonify({'error': 'Prohibido'}), 403
    try:
        if 'file' not in request.files:
            return jsonify({'status': 'error', 'message': 'No se proporcionó el archivo.'}), 400

        file = request.files['file']
        username = request.form.get('username')  # request.form para multipart/form-data.

        if not username:
            return jsonify({'status': 'error', 'message': 'Falta el nombre de usuario.'}), 400

        username = secure_filename(username)  # Asegura que sea un nombre normal.
        user_folder = os.path.join(UPLOAD_FOLDER, username)
        os.makedirs(user_folder, exist_ok=True)  # Crea el directorio si es necesario.

        filename = secure_filename(file.filename)
        if not filename:
            return jsonify({'status': 'error', 'message': 'Nombre de archivo no válido.'}), 400

        # Chequea las extensiones permitidas.
        if not allowed_file(filename):
            return jsonify({'status': 'error', 'message': 'Extensión no permitida. Admitidos: ' + ', '.join(sorted(ALLOWED_EXTENSIONS))}), 400

        file_path = os.path.join(user_folder, filename)

        # Chequea si el archivo ya existe.

        if os.path.exists(file_path):
            return jsonify({'status': 'error', 'message': 'El archivo ya existe.'}), 409 

        manager = VectorStorageManager()
        with manager.lock():
            if os.path.exists(file_path):
                return jsonify({'status': 'error', 'message': 'El archivo ya existe.'}), 409
            file.save(file_path)
            try:
                manager.insert_collection(file_path, username, already_locked=True)
            except Exception:
                os.remove(file_path)
                raise

        return jsonify({'status': 'success', 'file_path': file_path}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@app.route('/delete', methods=['POST'])
def delete_file():
    from eduai.api.documents import authorized
    if not authorized():
        return jsonify({'error': 'Prohibido'}), 403
    try:
        # Obtiene el nombre de usuario y nombre de archivo
        username = request.form.get('username')
        filename = request.form.get('filename')
        
        if not username or not filename:
            return jsonify({'status': 'error', 'message': 'Missing username or filename'}), 400

        # Sanitiza los inputs
        username = secure_filename(username)
        filename = secure_filename(filename)
        
        # Construye el path
        file_path = os.path.join(UPLOAD_FOLDER, username, filename)
        
        # Chequea si existe el path
        if not os.path.exists(file_path):
            return jsonify({'status': 'error', 'message': 'File does not exist'}), 404

        # Elimina el archivo
        manager = VectorStorageManager()
        with manager.lock():
            manager.delete_collection(username, filename, already_locked=True)
            os.remove(file_path)

        return jsonify({'status': 'success', 'message': 'Archivo y contenido eliminados correctamente.'}), 200

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

def installed_chat_model(name):
    """Valida nuevamente en Flask: no confiar solo en el selector Django."""
    if not isinstance(name, str) or not name:
        return False
    base_url = os.getenv('OLLAMA_HOST', 'http://localhost:11434').rstrip('/')
    response = requests.get(f'{base_url}/api/tags', timeout=(5, 12))
    response.raise_for_status()
    installed = {item.get('name') for item in response.json().get('models', [])}
    if name not in installed:
        return False
    detail = requests.post(
        f'{base_url}/api/show', json={'model': name}, timeout=(5, 12)
    )
    detail.raise_for_status()
    capabilities = detail.json().get('capabilities', [])
    return isinstance(capabilities, list) and 'completion' in capabilities


@socketio.on("message")
def handle_message(msg):
    #empieza conteo para tiempo de respuesta
    start = time.perf_counter()
    print(f"Mensaje recibido: {msg}")
    
    # Extrae el username y mensaje
    try:
        username, selected_files = verify_document_scope(msg.get('document_token'))
        if not selected_files:
            raise InvalidDocumentScope('Selecciona documentos disponibles antes de preguntar.')
    except InvalidDocumentScope as exc:
        emit('model_error', {'messageId': msg.get('messageId'), 'error': str(exc)})
        return
    sender_content = msg.get('sender_content')
    if not isinstance(sender_content, str) or not sender_content.strip() or len(sender_content) > 12000:
        emit('model_error', {'messageId': msg.get('messageId'), 'error': 'Mensaje vacío o demasiado largo.'})
        return
    receiver = str(msg.get('receiver') or '').strip()
    try:
        if not installed_chat_model(receiver):
            emit('model_error', {
                'messageId': msg.get('messageId'),
                'error': 'Este modelo no está instalado o no admite conversación. Selecciona un LLM.'
            })
            return
    except (requests.RequestException, ValueError, KeyError):
        emit('model_error', {
            'messageId': msg.get('messageId'),
            'error': 'No se pudo comprobar la disponibilidad de Ollama.'
        })
        return

    store = PDFStorage(username, selected_files)
    retriever = store.retrieve()

    model = ChooseModel(receiver)
    rag_chain = model.choose()
    rag_app = RAGApplication(retriever, rag_chain)
    
    try:
        rag_result = rag_app.run_with_sources(sender_content, username=username, filenames=selected_files)
        receiver_response = rag_result['answer']
        sources = rag_result['sources']
    except Exception:
        app.logger.exception('Error al ejecutar el modelo %s', receiver)
        emit('model_error', {
            'messageId': msg.get('messageId'),
            'error': 'La consulta falló. Comprueba el modelo y vuelve a intentarlo.'
        })
        return
    
    # Respuesta para django
    data = {
        'username': username,
        'sender_content': sender_content,
        'receiver': receiver,
        'receiver_response': receiver_response,
        'sources': sources
    }
    
    try:
        # Envia mensaje a Django para almacenar el mensaje
        response = requests.post(f"{DJANGO_BASE_URL}/dashboard/chat/save_mensaje/", json=data,
            headers={'X-EduAI-Internal-Token': os.getenv('AI_INTERNAL_TOKEN', '')}, timeout=15)
         # Debug output
        print(f"Status code: {response.status_code}")
        print(f"Response text: {response.text}")
        print(response.json())
    except Exception as e:
        print(f"Error posting message to Django: {e}")

    response = {
        'username': username,
        'sender_content': sender_content,
        'receiver': receiver,
        'receiver_response': receiver_response,
        'sources': sources,
        'messageId': msg.get('messageId')  # messageId para remover spinner
    }
    
    #calcular tiempo de respuesta
    duration = time.perf_counter() - start
    log_line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} | SOCKET message | {duration:.4f} sec | username={msg.get('username')}\n"
    with open(LOG_FILE, "a") as f:
        f.write(log_line)

    emit('message', response)
    
@app.route('/file', methods=['POST'])
def file():
    from eduai.api.documents import authorized
    if not authorized():
        return jsonify({'error': 'Prohibido'}), 403
    qgen = QuestionGenerator()
    try:
        username = request.form.get('username')
        archivo = request.form.get('archivo') 
        numero = request.form.get('numero')  
        tipo = request.form.getlist('tipo')  
        dificultad = request.form.get('dificultad', 'intermedia')
        
        # Genera las preguntas
        results = qgen.generate_all_types(types=tipo, number=numero, namespace=username, filename=archivo, dificultad=dificultad)

        # Path para guardar archivo
        folder_path = Path("exports") / username / archivo
        folder_path.mkdir(parents=True, exist_ok=True)

        pdf_path = folder_path / "generated_questions.pdf"
        docx_path = folder_path / "generated_questions.docx"

        create_questions_pdf(results, output_file=str(pdf_path))
        create_questions_docx(results, output_file=str(docx_path))

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zipf:
            zipf.write(pdf_path, arcname="generated_questions.pdf")
            zipf.write(docx_path, arcname="generated_questions.docx")

        zip_buffer.seek(0)

        # Retorna zip como respuesta
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=f"{archivo}_questions.zip",
            mimetype="application/zip"
        )
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/exam', methods=['POST'])
def exam():
    from eduai.api.documents import authorized
    if not authorized():
        return jsonify({'error': 'Prohibido'}), 403
    qgen = QuestionGenerator()
    try:
        username = request.form.get('username')
        archivo = request.form.get('archivo') 
        numero = request.form.get('numero')  
        tipo = request.form.getlist('tipo')  
        dificultad = request.form.get('dificultad', 'intermedia')
        
        print(archivo)

        # Genera las preguntas
        results = qgen.generate_all_types(types=tipo, number=numero, namespace=username, filename=archivo, dificultad=dificultad)

        # Retorna resultados
        return jsonify(results)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == "__main__":
    #EJECUTAR DESDE HOST PARA COMPLETAR LA COMUNICACION CON DJANGO
    #socketio.run(app, host="0.0.0.0", port=8080, debug=True)
    socketio.run(app, host=os.getenv("FLASK_HOST", "127.0.0.1"),
                 port=int(os.getenv("FLASK_PORT", "8080")),
                 debug=os.getenv("FLASK_DEBUG", "0") == "1")
    
# EDUAI_FUENTES_V1
