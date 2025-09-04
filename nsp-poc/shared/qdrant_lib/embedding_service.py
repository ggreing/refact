import os
from langchain_openai import OpenAIEmbeddings
from .utils import log_call

@log_call
def embed_texts(texts: list[str]) -> list[list[float]]:
    embedding_model = openai_embedding_model()
    response = embedding_model.embed_documents(texts)
    return response

@log_call
def openai_embedding_model(embedding_model_name: str = "text-embedding-3-small"):
    return OpenAIEmbeddings(
        model=embedding_model_name,
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )

@log_call
def embed_query(text: str) -> list[float]:
    """Embed a single query string to a vector."""
    model = openai_embedding_model()
    return model.embed_query(text)
