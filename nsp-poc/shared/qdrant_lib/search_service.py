import os
from typing import Union, List
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchAny
from .utils import log_call
from .embedding_service import embed_texts

@log_call
def retrieve(query: str, collection_names: Union[str, List[str]], limit: int = 5, score_threshold: float = None, file_hash_list: list[str] = None):
    if isinstance(collection_names, str):
        collection_list = [collection_names]
    else:
        collection_list = collection_names
    
    client = QdrantClient(
        url=os.getenv("QDRANT_URL")
    )
    
    query_vector = embed_texts([query])[0]

    query_filter = None
    if file_hash_list:
        query_filter = Filter(
            must=[
                FieldCondition(
                    key="file_hash",
                    match=MatchAny(any=file_hash_list)
                )
            ]
        )
    
    results = []
    for coll in collection_list:
        # Use search method instead of query_points
        search_kwargs = {
            "collection_name": coll,
            "query_vector": query_vector,
            "limit": limit,
            "with_payload": True,
        }
        if score_threshold is not None:
            search_kwargs["score_threshold"] = score_threshold
        if query_filter is not None:
            search_kwargs["query_filter"] = query_filter
            
        response = client.search(**search_kwargs)
        for point in response:
            results.append({
                "collection": coll,
                "payload": point.payload,
                "score": point.score
            })
    
    print(f"Search completed on collections {collection_list} for query '{query}' with {len(results)} results")
    return results