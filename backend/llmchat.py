from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_ollama import ChatOllama
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

BASE_DB_FOLDER = "chroma_dbs"

hf_embed_models = [
    "Alibaba-NLP/gte-large-en-v1.5",  #29
    "HIT-TMG/KaLM-embedding-multilingual-mini-instruct-v1.5", #33
    "mixedbread-ai/mxbai-embed-large-v1", #37,
    "intfloat/multilingual-e5-large-instruct", #54
    "BAAI/bge-base-en-v1.5", #55
    "nomic-ai/nomic-embed-text-v1", #65
    "sentence-transformers/all-MiniLM-L12-v2" #140
]

ollama_models = [
    "gemma3:4b",            
    "llama3.2"
]
embeddings = HuggingFaceEmbeddings(model_name=hf_embed_models[6])


class PDFStorage:
    def __init__(self, username):
        self.username = username

    def retrieve(self):

        vector_store = Chroma(
            collection_name=f"user_{self.username}_collection",
            persist_directory=BASE_DB_FOLDER,
            embedding_function=embeddings
        )

        retriever = vector_store.as_retriever(
            search_type = "similarity_score_threshold",
            search_kwargs = {
                "k":5,
                "score_threshold":0.1,
            }
        )      
        return retriever

# Define la plantilla del prompt para el LLM
prompt = PromptTemplate(
    template="""You are a helpful assistant that answers questions using only the provided documents.

    **Key Rules:**
    - Respond in the SAME language as the question
    - Base answers strictly on the documents provided
    - Be concise but complete
    - If information isn't in the documents, say "I don't have any information about that"
    - Synthesize information from multiple documents when relevant
    
    Question: {question}
    Documents: {documents}
    Answer:
    """,
    input_variables=["question", "documents"],
)

class ChooseModel:
    def __init__(self, model: int):
        self.model = model

    def choose(self):
        llm = ChatOllama(
            model=ollama_models[self.model],
            temperature=0.1,
        )
        # Crea una cadena combinando la plantilla del promp y el LLM
        rag_chain = prompt | llm | StrOutputParser()

        return rag_chain

# Clase para aplicación RAG
class RAGApplication:
    def __init__(self, retriever, rag_chain):
        self.retriever = retriever
        self.rag_chain = rag_chain
    def run(self, question):
        # Obtiene los docuemntos relevantes
        documents = self.retriever.invoke(question)
        # Extrae el contenido de los documentos
        doc_texts = "\\n".join([doc.page_content for doc in documents])
        # Obtiene la respuesta del LLM
        answer = self.rag_chain.invoke({"question": question, "documents": doc_texts})
        return answer