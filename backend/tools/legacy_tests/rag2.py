from langchain_community.document_loaders import PDFPlumberLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain
from langchain.chains import LLMChain
from langchain_core.output_parsers import StrOutputParser

folder_path = "test_dbs"
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
text_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=100, length_function=len, is_separator_regex=False)

llm = OllamaLLM(model=ollama_models[0])

#vector_store = Chroma(persist_directory=folder_path, embedding_function=embeddings)
vector_store = Chroma( collection_name=f"user_damian_collection",persist_directory=folder_path, embedding_function=embeddings)
#collection = vector_store._collection
#documents = collection.get(where={"source": "uploads/damian/philo.pdf"}, include=["documents"])
collection = vector_store._collection
documentsV1 = collection.get(where={"source": "uploads/damian/philo.pdf"})['documents']

print("-------------------PRINTING DOCUEMNTS V1----------------")

doc_texts = "\\n".join([' '.join(p.split()) for p in documentsV1])
print(doc_texts)
print("------------------FIN------------------------------")
print("CREATING CHAIN")
#retriever = vector_store.as_retriever(
#    search_type = "similarity_score_threshold",
#    search_kwargs = {
#        "k":5,
#        "score_threshold":0.1,
#    }
#)


#documents = retriever.invoke("what did aristotle say?")
# documents = retriever.invoke({}) // vacio porque en el retriver.invoke ya esoty llamando a los documentos del archivo especiifcado en la coleccion
#print(f'docs len: {len(documents)}')
# Extract content from retrieved documents
#doc_texts = "\\n".join([doc.page_content for doc in documents])

#print("-------------------PRINTING DOC_TEXTS----------------")
#print(doc_texts)

#print("------------------FIN------------------------------")

prompt = PromptTemplate(
    template="""You are an assistant for question-answering tasks.

        Given the input text, your task is to generate 10 multiple-choice questions. 
        Each question must include:
        - 4 answer options
        - One correct answer
        - A short explanation of the correct answer

        Format the output strictly as JSON like this:

        {{
            "questions": [
                {{
                "question": "Your question here",
                "options": ["option1", "option2", "option3", "option4"],
                "correct_answer": "Correct option text",
                "explanation": "Brief explanation of why this answer is correct"
                }},
                ...
            ]
        }}

        Text:
        {documents}
        """,
    input_variables=["documents"]
)

rag_chain = prompt | llm | StrOutputParser()

question = "what did aristotle say?"

answer = rag_chain.invoke({"documents": doc_texts})

print("Question:", question)
print("Answer:", answer)