import os
import logging
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from filecontentextractor import FileContentExtractor
from langchain_core.documents import Document


# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VectorStorageManager:
    UPLOAD_FOLDER = "uploads"
    BASE_DB_FOLDER = "chroma_dbs"

    hf_embed_models = [
        "Alibaba-NLP/gte-large-en-v1.5",
        "HIT-TMG/KaLM-embedding-multilingual-mini-instruct-v1.5",
        "mixedbread-ai/mxbai-embed-large-v1",
        "intfloat/multilingual-e5-large-instruct",
        "BAAI/bge-base-en-v1.5",
        "nomic-ai/nomic-embed-text-v1",
        "sentence-transformers/all-MiniLM-L12-v2"
    ]

    def __init__(self, model_index=6):
        os.makedirs(self.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(self.BASE_DB_FOLDER, exist_ok=True)

        logger.info("Initializing VectorStorageManager with model index %d", model_index)

        self.extractor = FileContentExtractor()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1024, chunk_overlap=80, length_function=len, is_separator_regex=False
        )
        self.embeddings = HuggingFaceEmbeddings(model_name=self.hf_embed_models[model_index])

    def insert_collection(self, file_path, username):
        try:
            logger.info("Inserting document for user '%s': %s", username, file_path)
            
            text = self.extractor.get_text(file_path)
            doc = Document(page_content=text, metadata={"source": f"uploads/{username}/{os.path.basename(file_path)}"})
            chunks = self.text_splitter.split_documents([doc])

            Chroma.from_documents(
                documents=chunks,
                embedding=self.embeddings,
                persist_directory=self.BASE_DB_FOLDER,
                collection_name=f"user_{username}_collection"
            )
            logger.info("Successfully inserted document into collection.")
        except Exception as e:
            logger.error("Failed to insert document for user '%s': %s", username, str(e), exc_info=True)

    def delete_collection(self, username, filename):
        try:
            logger.info("Deleting document '%s' from collection of user '%s'", filename, username)
            vectorstore = Chroma(
                collection_name=f"user_{username}_collection",
                persist_directory=self.BASE_DB_FOLDER
            )
            collection = vectorstore._collection
            result = collection.get(where={"source": f"uploads/{username}/{filename}"})
            ids = result.get('ids', [])

            if ids:
                collection.delete(ids)
                logger.info("Successfully deleted %d document(s) from collection.", len(ids))
            else:
                logger.warning("No matching documents found to delete.")
        except Exception as e:
            logger.error("Failed to delete document for user '%s': %s", username, str(e), exc_info=True)

    def get_docs(self, username, filename):
        vector_store = Chroma( collection_name=f"user_{username}_collection",persist_directory=self.BASE_DB_FOLDER, embedding_function=self.embeddings)
        collection = vector_store._collection
        docs = collection.get(where={"source": f"uploads/{username}/{filename}"})['documents']
        return docs