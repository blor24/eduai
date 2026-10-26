from flask import Flask, request
import openai
import PyPDF2
from chromadb.config import Settings
import chromadb

client = chromadb.Client(Settings(chroma_db_impl="duckdb+parquet", anonymized_telemetry=False))

app = Flask()

def extract_text_from_pdf(file_path):
    text = ""
    with open(file_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        for page in reader.pages:
            text += page.extract_text()
    return text

def generate_embeddings(text):
    response = openai.Embedding.create(
        input=text,
        model="text-embedding-ada-002"
    )
    return response['data'][0]['embedding']


def get_user_collection(user_identifier, client):
    collection_name = f"user_{user_identifier}_collection"
    return client.get_or_create_collection(name=collection_name)


def insert_pdf_to_user_collection(file_path, user_identifier, client):
    # Get or create the user's collection
    collection = get_user_collection(user_identifier, client)

    # Extract text from PDF
    text = extract_text_from_pdf(file_path)

    # Split text into chunks (if necessary)
    chunks = [text[i:i+500] for i in range(0, len(text), 500)]

    # Generate embeddings and insert into the user's collection
    for i, chunk in enumerate(chunks):
        embedding = generate_embeddings(chunk)
        collection.add(
            documents=[chunk],
            embeddings=[embedding],
            metadatas=[{"chunk_id": i, "source": file_path}],
            ids=[f"{file_path}_chunk_{i}"]
        )

@app.route('/upload', methods=['POST'])
def upload_pdf():
    user_identifier = request.form.get('user_identifier')  # Assume user provides this
    if not user_identifier:
        return "User identifier is required", 400

    if 'file' not in request.files:
        return "No file uploaded", 400

    file = request.files['file']
    file_path = f"./uploads/{file.filename}"
    file.save(file_path)
    
    # Insert into user's collection
    insert_pdf_to_user_collection(file_path, user_identifier, client)
    
    return f"File processed and added to {user_identifier}'s collection", 200

def query_user_collection(user_identifier, query, client):
    collection = get_user_collection(user_identifier, client)
    results = collection.query(
        query_texts=[query],
        n_results=5  # Number of results to retrieve
    )
    return results

@app.route('/query', methods=['POST'])
def query_collection():
    user_identifier = request.form.get('user_identifier')
    query = request.form.get('query')

    if not user_identifier or not query:
        return "User identifier and query are required", 400

    results = query_user_collection(user_identifier, query, client)
    return {"results": results}, 200