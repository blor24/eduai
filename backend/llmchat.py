"""Chat RAG; consulta siempre el índice de embeddings activo en Django."""
import os
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_ollama import ChatOllama
from vectorstorage import VectorStorageManager
from ai_runtime import config

prompt = PromptTemplate(
    template='''You are a helpful assistant that answers questions using only the provided documents.
Respond in the same language as the question. If the documents do not answer it,
say that you do not have enough information. Never invent facts.
Question: {question}
Documents: {documents}
Answer:''', input_variables=['question', 'documents'])


class PDFStorage:
    def __init__(self, username):
        self.username = username

    def retrieve(self):
        return VectorStorageManager().retriever(self.username)


class ChooseModel:
    def __init__(self, model_name):
        self.model_name = model_name

    def choose(self):
        llm = ChatOllama(model=self.model_name, temperature=0.1,
                         base_url=os.getenv('OLLAMA_HOST', 'http://ollama:11434'),
                         num_ctx=int(os.getenv('CHAT_NUM_CTX', '4096')))
        return prompt | llm | StrOutputParser()


class RAGApplication:
    def __init__(self, retriever, rag_chain):
        self.retriever, self.rag_chain = retriever, rag_chain

    def run(self, question):
        documents = self.retriever.invoke(question)
        texts = '\n'.join(doc.page_content for doc in documents)
        return self.rag_chain.invoke({'question': question, 'documents': texts})
