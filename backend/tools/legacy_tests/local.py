from langchain_community.document_loaders import PDFPlumberLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain
from langchain.chains import LLMChain

folder_path = "db_local"
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
    "qwen2.5:1.5b",    
    "qwen2.5:0.5b",         
    "llama3.2:1b",         
    "llama3.2"
]
embeddings = HuggingFaceEmbeddings(model_name=hf_embed_models[6])
text_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=100, length_function=len, is_separator_regex=False)

llm = OllamaLLM(model=ollama_models[3])

prompt = PromptTemplate.from_template(
    """
    <s>[INST] 
    You are a helpful AI assistant who is an expert in answering questions factually and concisely. 
    Your task is to answer the user's demand using the provided context. If the context is insufficient, 
    reply with "I'm sorry, I don't have enough information to answer that." 

    Context: {context}
    Question: {input}
    Answer:
    [/INST]</s>
    """
)

def carga_docs(documento):
    loader = PDFPlumberLoader(documento)
    docs = loader.load_and_split()
    print(f'docs len: {len(docs)}')

    chunks = text_splitter.split_documents(docs)
    print(f'chunks length: {len(chunks)}')

    vector_store = Chroma.from_documents(documents=chunks, embedding=embeddings, persist_directory=folder_path)

    response = {
        "status": "Success",
        "doc_length": len(docs),
        "chunks": len(chunks),
    }
    return response


""" doc = "./pdf/phil.pdf"

carga_docs(documento=doc) """


def preguntar(query):
    vector_store = Chroma(persist_directory=folder_path, embedding_function=embeddings)
    print("CREATING CHAIN")
    retriever = vector_store.as_retriever(
        search_type = "similarity_score_threshold",
        search_kwargs = {
            "k":20,
            "score_threshold":0.1,
        }
    )

    print("DOCUMENT CHAIN")
    document_chain = create_stuff_documents_chain(llm, prompt)
    chain = create_retrieval_chain(retriever, document_chain)

    result = chain.invoke({"input": query})
    print("RESPUESTA:")
    answer = {"answer": result["answer"]}
    return answer

""" start_time = time.time()

answer = preguntar("make 5 true or false questions with their answer about the special fields of philosophy")
print(answer)
print("--- %s minutes ---" % ((time.time() - start_time)/60)) """

prompt2 = PromptTemplate.from_template(
    """Based on the following document content, generate 5 educational questions:
    Document content: {context}
    
    Generate a mix of:
    - Factual recall questions
    - Understanding/comprehension questions
    - Application questions
    """
)

def generar_preguntas():
    try:
        # Initialize vector store
        vector_store = Chroma(
            persist_directory=folder_path, 
            embedding_function=embeddings,
        )
        
        # Create retriever without debug printing
        retriever = vector_store.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs={
                "k": 5,
                "score_threshold": 0.1,
            }
        )
        
        # Create chain
        document_chain = create_stuff_documents_chain(llm, prompt2)
        chain = create_retrieval_chain(retriever, document_chain)
        
        # Get only the answer from the result
        result = chain.invoke({"input": "Generate educational questions"})
        
        # Return only the answer part
        if "answer" in result:
            return result["answer"]
        else:
            return {"error": "No answer generated"}
            
    except Exception as e:
        return {"error": str(e)}

# Example Usage
if __name__ == "__main__":
    # Load and preprocess document
    #doc_path = "./pdf/phil.pdf"
    #print("Loading and splitting document...")
    #carga_response = carga_docs(documento=doc_path)
    #print(carga_response)

    # Generate educational questions
    print("Generating educational questions...")
    questions = generar_preguntas()
    print(questions)