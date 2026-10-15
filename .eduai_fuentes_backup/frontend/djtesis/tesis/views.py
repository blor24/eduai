from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from .forms import CrearUserForm, LoginForm
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
import requests
from django.http import JsonResponse
from .models import Archivo, Mensaje, Estadistica
from django.contrib.auth.models import User
from datetime import datetime
from django.views.decorators.csrf import csrf_exempt
import json
import os
FLASK_BASE_URL = os.environ.get("FLASK_BASE_URL", "http://localhost:8080").rstrip("/")
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.db.models import Count, Avg, Sum
from django.views.decorators.cache import never_cache

from .ollama_api import list_models

def index(request):
    register_form = CrearUserForm()
    login_form = LoginForm()

    if request.method == 'POST':
        # Chequea cual form fue ejecutado.
        if 'register_submit' in request.POST:  
            register_form = CrearUserForm(request.POST)
            if register_form.is_valid():
                register_form.save()
                messages.success(request, "Cuenta creada. Por favor, inicie sesión")
                return redirect('index')
            else:
                # Conserva los errores del formulario para mostrarlos al usuario.
                messages.warning(request, "Creación fallida. Revise los datos ingresados.")
        elif 'login_submit' in request.POST: 
            login_form = LoginForm(request, data=request.POST)
            if login_form.is_valid():
                username = request.POST.get('username')
                password = request.POST.get('password')
                user = authenticate(request, username=username, password=password)
                if user is not None:
                    login(request, user)
                    if request.GET.get('next','/')== '/':
                        return redirect('dashboard')
                    else:
                        return redirect(request.GET.get('next','/'))
            else:
                messages.warning(request, "Usuario no existe o contraseña mal ingresada.")
                return redirect('index')
    context = {
        'register_form': register_form,
        'login_form': login_form
    }
    return render(request, "tesis/index.html", context=context)

def logout_user(request):
    logout(request)
    return redirect('index')

@login_required(login_url='index')
def dashboard(request):
    user = request.user
    
    # Estadisticas basicas
    total_files = Archivo.objects.filter(user=user).count()
    total_messages = Mensaje.objects.filter(sender=user).count()
    
    # Estadisticas recientes (ultimos 30 dias)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_files = Archivo.objects.filter(user=user, fecha_carga__gte=thirty_days_ago).count()
    recent_messages = Mensaje.objects.filter(sender=user, timestamp__gte=thirty_days_ago).count()
    
    # Estadisticas de estudio
    estadisticas = Estadistica.objects.filter(user=user)
    avg_score = estadisticas.filter(puntaje__isnull=False).aggregate(Avg('puntaje'))['puntaje__avg'] or 0
    total_study_time = estadisticas.filter(tiempo_estudio__isnull=False).aggregate(Sum('tiempo_estudio'))['tiempo_estudio__sum'] or 0
    total_chat_time = estadisticas.filter(tiempo_chat__isnull=False).aggregate(Sum('tiempo_chat'))['tiempo_chat__sum'] or 0
    total_exams = estadisticas.filter(tiempo_estudio__isnull=True, tiempo_chat__isnull=True).count()
    
    # Tipo de archivos
    file_types = Archivo.objects.filter(user=user).values('tipo').annotate(
        count=Count('tipo')
    ).order_by('-count')
    
    # Actividad reciente (ultimos 10)
    recent_files_list = Archivo.objects.filter(user=user).order_by('-fecha_carga')[:5]
    recent_messages_list = Mensaje.objects.filter(sender=user).order_by('-timestamp')[:5]
    recent_stats = Estadistica.objects.filter(user=user, tiempo_estudio__isnull=True, tiempo_chat__isnull=True).order_by('-momento_uso')[:5]
    
    # Datos de progreso (ultimos 7 dias)
    progress_data = []
    chat_data = []
    labels = []
    
    for i in range(6, -1, -1):  # Last 7 days
        date = timezone.now() - timedelta(days=i)
        day_stats = Estadistica.objects.filter(
            user=user, 
            momento_uso__date=date.date()
        )
        
        avg_score_day = day_stats.aggregate(Avg('puntaje'))['puntaje__avg'] or 0
        total_study_day = day_stats.aggregate(Sum('tiempo_estudio'))['tiempo_estudio__sum'] or 0
        
        progress_data.append(round(avg_score_day, 1))
        chat_data.append(round(total_study_day, 1))
        labels.append(date.strftime('%d/%m'))

    # Dias activo
    active_days = Estadistica.objects.filter(user=user).values('momento_uso__date').distinct().count()
    
    # Estadisticas para las cards
    stats = {
        'total_files': total_files,
        'total_messages': total_messages,
        'total_exams': total_exams,
        'avg_score': round(avg_score, 1) if avg_score else 0,
        'total_study_time': round(total_study_time, 1),
        'total_chat_time': round(total_chat_time, 1),
        'active_days': active_days,
        'recent_files': recent_files,
        'recent_messages': recent_messages,
    }
    
    # Prepara datos para graficos
    chart_data = {
        'progress_labels': labels,
        'progress_scores': progress_data,
        'progress_study_time': chat_data,
        'file_types_labels': [ft['tipo'] for ft in file_types],
        'file_types_data': [ft['count'] for ft in file_types],
    }
    
    # Almacena las actvidades
    recent_activities = []
    
    # Añade archivos recientes
    for file in recent_files_list:
        recent_activities.append({
            'type': 'upload',
            'icon': 'bi-upload',
            'color': 'primary',
            'title': f'Subido: {file.nombre}',
            'time': file.fecha_carga,
            'extra': f'Tipo: {file.tipo}'
        })
    
    # Añade examnes recientes
    for stat in recent_stats:
        recent_activities.append({
            'type': 'exam',
            'icon': 'bi-pencil-square',
            'color': 'warning',
            'title': 'Examen completado',
            'time': stat.momento_uso,
            'extra': f'Puntaje: {stat.puntaje}%'
        })
    
    # Añade mensajes recientes
    for msg in recent_messages_list[:3]:  # Muestra solo 3
        recent_activities.append({
            'type': 'chat',
            'icon': 'bi-chat-dots',
            'color': 'success',
            'title': f'Chat con {msg.receiver}',
            'time': msg.timestamp,
            'extra': f'Mensaje: {msg.sender_content[:50]}...' if len(msg.sender_content) > 50 else msg.sender_content
        })
    
    # Ordena actividades por tiempo y toma los 5 mas recientes 
    recent_activities.sort(key=lambda x: x['time'], reverse=True)
    recent_activities = recent_activities[:5]

    context = {
        'page': 'dashboard',
        'user': user.username,
        'stats': stats,
        'chart_data': json.dumps(chart_data),
        'recent_activities': recent_activities,
        'file_types': file_types,
    }
    return render(request, "tesis/dashboard.html", context)
    
@never_cache
@login_required(login_url='index')
def available_ollama_models(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'Método no permitido.'}, status=405)
    try:
        return JsonResponse({'models': [item['name'] for item in list_models()]})
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return JsonResponse({'error': 'No se pudo consultar Ollama.'}, status=503)

@login_required(login_url='index')
def chat(request):
    user = request.user.username
    messages = Mensaje.objects.filter(sender_id=request.user).order_by('timestamp')[:50]  # Load last 50 messages
    try:
        models = list_models()
    except (requests.RequestException, ValueError, KeyError, TypeError):
        models = []
    context = {'page':'chat', 'models': models, 'messages': messages, 'username': user}
    return render(request, "tesis/chat.html", context)

@login_required(login_url='index')
def archivos(request):
    if request.method =='POST':

        if 'upload_submit' in request.POST:
            #Obtiene el username y file del request
            username = request.user.username
            file_obj = request.FILES.get('file')
            
            if not username or not file_obj:
                messages.error(request, 'Selecciona un archivo para cargar.')
                return redirect('archivos')
            
            flask_url = f"{FLASK_BASE_URL}/upload" 
            
            # Prepara el payload de datos.
            data = {
                'username': username,
            }
            # Cuando se envian archivos, la libreria requests espera una tupla: (filename, fileobj, content_type)
            files = {
                'file': (file_obj.name, file_obj, file_obj.content_type),
            }

            try:
                # POST al Flask server.
                response = requests.post(flask_url, data=data, files=files,
                    headers={'X-EduAI-Internal-Token': os.environ.get('AI_INTERNAL_TOKEN', '')},
                    timeout=180)
                response.raise_for_status()  # Genera un HTTPError si la petición HTTP retorna un codigo fallido.

                saved_filename = os.path.basename(response.json()['file_path'])
                archivo = Archivo(user=request.user, nombre=saved_filename,
                    tipo=os.path.splitext(saved_filename)[1].lower(), fecha_carga=datetime.now())
                archivo.save()
                messages.success(request, "Archivo y contenido almacenados correctamente.")
            except requests.exceptions.RequestException as e:
                error_data = response.json()
                error_message = error_data.get('message', 'Ocurrió un error.')
                messages.error(request, error_message)
        elif 'delete_submit' in request.POST:
            username = request.user.username
            id_archivo = request.POST.get('id-archivo')
            filename = request.POST.get('nombre-archivo')
            
            instancia = Archivo.objects.filter(user=request.user, id=id_archivo).first()
            if instancia is None:
                messages.error(request, 'No existe ese archivo en tu biblioteca.')
                return redirect('archivos')
            filename = instancia.nombre  # no confiar en el campo oculto del formulario

            if not username or not filename:
                messages.error(request, 'Missing username or filename.')

            flask_url = f"{FLASK_BASE_URL}/delete"

            data = {
                'username': username,
                'filename': filename,
            }

            try:
                response = requests.post(flask_url, data=data,
                    headers={'X-EduAI-Internal-Token': os.environ.get('AI_INTERNAL_TOKEN', '')},
                    timeout=45)
                response_data = response.json()

                if response.status_code == 200 and response_data.get('status') == 'success':
                    instancia.delete()
                    messages.success(request, response_data.get('message', 'Archivo eliminado correctamente.'))
                else:
                    messages.error(request, response_data.get('message', 'Error al eliminar el archivo.'))
            except requests.exceptions.RequestException as e:
                messages.error(request, f"Request error: {e}")
    
    subidos = Archivo.objects.filter(user=request.user)
    context = {'page':'archivos', 'subidos': subidos}

    return render(request, "tesis/archivos.html", context)

@never_cache
@login_required(login_url='index')
def examen(request):
    subidos = Archivo.objects.filter(user=request.user)
    username = request.user.username

    if request.method == 'POST':
        if 'submit_quiz' in request.POST:
            if not request.session.get('quiz_questions'):
                messages.error(request, "Este examen ya ha sido enviado o ha expirado.")
                return redirect('examen')
            preguntas = json.loads(request.session.get('quiz_questions', '{}'))
            respuestas_usuario = request.POST
            puntaje = 0
            total = 0
            resultados = []

            for tipo, data in preguntas.items():
                for idx, pregunta in enumerate(data["questions"]):
                    key = f"q_{tipo}_{idx}"

                    if tipo == 'emparejar' and 'terms' in pregunta and 'concepts' in pregunta:
                        user_matches = []
                        correct_matches = []

                        for match_idx, term in enumerate(pregunta["terms"]):
                            match_key = f"q_{tipo}_{idx}_{match_idx}"
                            user_value = respuestas_usuario.get(match_key, "").strip()
                            user_matches.append(user_value)
                            correct_matches.append(pregunta["concepts"][match_idx])

                        is_correct = all(u.lower() == c.lower() for u, c in zip(user_matches, correct_matches))

                        resultado = {
                            "question": "Emparejar los conceptos:",
                            "pairs": [
                                {
                                    "term": t,
                                    "user": u,
                                    "correct": c
                                } for t, u, c in zip(pregunta["terms"], user_matches, correct_matches)
                            ],
                            "is_correct": is_correct,
                            "explanation": "Relación esperada entre términos y conceptos."
                        }
                    else:
                        key = f"q_{tipo}_{idx}"
                        user_answer = respuestas_usuario.get(key, "").strip()
                        correct = pregunta["correct_answer"].strip()

                        resultado = {
                            "question": pregunta["question"],
                            "user_answer": user_answer,
                            "correct_answer": correct,
                            "is_correct": user_answer.lower() == correct.lower(),
                            "options": pregunta.get("options", []),
                            "explanation": pregunta["explanation"]
                        }

                    resultados.append(resultado)
                    total += 1
                    if resultado["is_correct"]:
                        puntaje += 1
                    
            puntaje_final = (puntaje * 100)/sum(len(grupo.get("questions", [])) for grupo in preguntas.values())
            print("PUNTAJE FINAL"+str(puntaje_final))
            Estadistica.objects.create(user=request.user,puntaje=puntaje_final)
            request.session.pop('quiz_questions', None)
            return render(request, "tesis/resultado.html", {
                "resultados": resultados,
                "puntaje": puntaje,
                "total": total
            })
        elif 'generate_quiz' in request.POST:
            archivo = Archivo.objects.get(user=request.user, id=int(request.POST.get('archivoSelect')))
            num_preguntas = int(request.POST.get('numPreguntas'))
            tipo_preguntas = request.POST.getlist('tipoPregunta')

            flask_url = f"{FLASK_BASE_URL}/exam"
            
            data = {
                'username': username,
                'archivo': archivo,
                'numero': num_preguntas,
                'tipo': tipo_preguntas
            }

            try:
                response = requests.post(flask_url, data=data,
                headers={'X-EduAI-Internal-Token': os.environ.get('AI_INTERNAL_TOKEN', '')},
                timeout=300)
                response.raise_for_status()

                if response.status_code == 200:
                    preguntas = response.json() 
                    request.session['quiz_questions'] = json.dumps(preguntas)
                    context = {'page':'examen', 'subidos': subidos, 'preguntas':preguntas, 'ready':1}

                    return render(request, "tesis/examen.html", context)
                else:
                    error_data = response.json()
                    error_message = error_data.get('message', 'Ocurrió un error.')
                    messages.error(request, error_message)
            except Exception as e:
                messages.error(request, f"Error al generar preguntas: {e}")
    context = {'page':'examen', 'subidos': subidos}
    return render(request, "tesis/examen.html", context)

@login_required(login_url='index')
def resultados(request):
    return render(request, "tesis/resultado.html")

@login_required(login_url='index')
def generar(request):
    subidos = Archivo.objects.filter(user=request.user)
    username = request.user.username
    pdf_url = None  # se pasa al template

    if request.method == 'POST':
        archivo = Archivo.objects.get(user=request.user, id=int(request.POST.get('archivoSelect')))
        nombre_archivo = os.path.splitext(archivo.nombre)[0]  # elimina la extension del archivo
        num_preguntas = int(request.POST.get('numPreguntas'))
        tipo_preguntas = request.POST.getlist('tipoPregunta')

        flask_url = f"{FLASK_BASE_URL}/file"

        data = {
            'username': username,
            'archivo': archivo,
            'numero': num_preguntas,
            'tipo': tipo_preguntas
        }

        try:
            response = requests.post(flask_url, data=data,
                headers={'X-EduAI-Internal-Token': os.environ.get('AI_INTERNAL_TOKEN', '')},
                timeout=300)
            response.raise_for_status()

            if response.headers.get("Content-Type") == "application/zip":
                export_dir = os.path.join(settings.MEDIA_ROOT, "exports", username, nombre_archivo)
                os.makedirs(export_dir, exist_ok=True)
                zip_path = os.path.join(export_dir, "generated_questions.zip")

                # Guarda zip
                with open(zip_path, 'wb') as f:
                    f.write(response.content)

                # Extrae both PDF + DOCX localmente
                import zipfile
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(export_dir)

                pdf_url = f"{settings.MEDIA_URL}exports/{username}/{nombre_archivo}/generated_questions.pdf"
                docx_url = f"{settings.MEDIA_URL}exports/{username}/{nombre_archivo}/generated_questions.docx"

                messages.success(request, "Archivos PDF y DOCX generados correctamente.")

            else:
                messages.error(request, "La respuesta no fue un archivo PDF.")

        except requests.exceptions.RequestException as e:
            messages.error(request, f"Error al generar el PDF: {str(e)}")

    context = {
        'page': 'generar',
        'subidos': subidos,
        'pdf_url': pdf_url if 'pdf_url' in locals() else None,
        'docx_url': docx_url if 'docx_url' in locals() else None,
    }

    return render(request, "tesis/genera-preguntas.html", context)

@login_required(login_url='index')
def cuenta(request):
    user_name = request.user.username
    user_email = request.user.email
    password_form = PasswordChangeForm(request.user)
    
    if request.method == 'POST':
        password_form = PasswordChangeForm(request.user, request.POST)
        if password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user)  # Importante
            messages.success(request, 'Su contraseña fue cambiada correctamente!')
            return redirect('cuenta')
        else:
            messages.error(request, 'Asegúrese de cumplir con las instrucciones.')
    
    context = {'user_name':user_name, 'user_email': user_email, 'password_form': password_form}
    return render(request, "tesis/cuenta.html", context)

@csrf_exempt
def save_mensaje(request):
    import hmac
    secret = os.environ.get('AI_INTERNAL_TOKEN', '')
    if not secret or not hmac.compare_digest(secret, request.headers.get('X-EduAI-Internal-Token', '')):
        return JsonResponse({'error': 'Prohibido'}, status=403)
    if request.method == 'POST':
        data = json.loads(request.body)
        
        # Extrae informacion del sender
        sender_username = data.get('username')
        sender_message = data.get('sender_content')
        receiver_name = data.get('receiver')
        receiver_reply = data.get('receiver_response')
        
        # Encuentra el ojeto user
        try:
            sender_user = User.objects.get(username=sender_username)
        except User.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': f'Sender not found: {sender_username}'}, status=404)

        # Crea y guarba objeto mensaje
        mensaje = Mensaje.objects.create(
            sender=sender_user,
            sender_content=sender_message,
            receiver = receiver_name,
            receiver_response=receiver_reply
        )

        return JsonResponse({'status': 'success', 'message_id': mensaje.id})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)

@csrf_exempt
def track_session(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            duration = float(data.get("duration", 0))
            page = data.get("page")

            if page == "chat":
                Estadistica.objects.create(
                    user=request.user,
                    tiempo_chat=duration
                )
            elif page == "examen":
                Estadistica.objects.create(
                    user=request.user,
                    tiempo_estudio=duration
                )
            return JsonResponse({"status": "ok"})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)
    return JsonResponse({"status": "invalid request"}, status=405)
