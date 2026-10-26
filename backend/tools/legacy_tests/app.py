from flask import Flask, request
from langchain_ollama import OllamaLLM
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from langchain_community.document_loaders import PDFPlumberLoader
from langchain_chroma import Chroma
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain
from langchain.prompts import PromptTemplate
import requests

folder_path = "db"
app = Flask(__name__)
llm = OllamaLLM(model="llama3.2")
embeddings = FastEmbedEmbeddings()
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1024, chunk_overlap=80, length_function=len, is_separator_regex=False)
prompt = PromptTemplate.from_template(
    """
    <s>[INST] You are a helpful AI assistant who is expert in answering questions. Your task is to answer user's questions as factually as possible. You will be given enough context with information to answer the user's questions. Find the conext:[/INST]</s>
    [INST] 
        Context: {context}
        Question: {input}
        Answer:
    [/INST]
    """)


#QUERY A LLM
@app.route("/ai", methods=["POST"])
def ask():
    content = request.get_json(silent=True)
    print(f'query:{content}')

    response = llm.invoke(f'{content["query"]}')

    answer = {"answer": response}
    return answer

@app.route("/askpdf", methods=["POST"])
def askpdf():
    content = request.get_json(silent=True)
    query = content["query"]
    print(f'query:{content}')

    print("LOADING VECTOR STORE")
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
    print(result)
    answer = {"answer": result["answer"]}
    return answer

#CARGA D ARCHIVOS
@app.route("/pdf", methods=["POST"])
def pdf():
    file = request.files["file"]
    file_name = file.filename
    save_file = "pdf/" + file_name
    file.save(save_file)

    loader = PDFPlumberLoader(save_file)
    docs = loader.load_and_split()
    print(f'docs len: {len(docs)}')

    chunks = text_splitter.split_documents(docs)
    print(f'chunks length: {len(chunks)}')

    vector_store = Chroma.from_documents(documents=chunks, embedding=embeddings, persist_directory=folder_path)

    response = {
        "status": "Success",
        "filename": file_name,
        "doc_length": len(docs),
        "chunks": len(chunks),
    }
    return response

def start_app():
    app.run(host="localhost", port=8080, debug=True)

if __name__ == "__main__":
    start_app()