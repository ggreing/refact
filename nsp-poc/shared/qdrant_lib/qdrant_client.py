import datetime
import os
import uuid
import hashlib
import csv
from typing import Optional, List, Dict
from zoneinfo import ZoneInfo
import logging
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from .utils import log_call
from .file_handler import load_file, chunk_text_with_metadata
from .embedding_service import embed_texts, embed_query
from pydantic import BaseModel, Field
from ..mongodb_lib.client import MongoDBClient as mdb

KST = ZoneInfo("Asia/Seoul")
logger = logging.getLogger(__name__)

@log_call
def upload_to_qdrant(chunks: list[str], embeddings: list[list[float]], metadata_list: list[dict], collection_name: str, file_hash: str = None):
    client = QdrantClient(
        url=os.getenv("QDRANT_URL")
    )

    if collection_name not in [c.name for c in client.get_collections().collections]:
        client.recreate_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=len(embeddings[0]), distance=Distance.COSINE)
        )

    upload_date = datetime.datetime.now().isoformat()

    points = []
    for text, vec, meta in zip(chunks, embeddings, metadata_list):
        payload = {
            "text": text,
            "upload_date": upload_date,
            "metadata": {},
            "file_hash": file_hash,
        }
        # Merge arbitrary metadata keys (page/line still supported)
        if isinstance(meta, dict):
            payload["metadata"].update(meta)

        points.append(PointStruct(id=str(uuid.uuid4()), vector=vec, payload=payload))
    
    # Upload in batches to avoid timeout
    batch_size = 50
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        logger.info(f"Uploading batch {i//batch_size + 1}/{(len(points)-1)//batch_size + 1}: {len(batch)} points")
        client.upsert(collection_name=collection_name, points=batch)

@log_call
def process_and_upload(file_path: str, collection_name: str, file_hash: str):
    docs = load_file(file_path)
    chunks, metadatas = chunk_text_with_metadata(docs)
    embeddings = embed_texts(chunks)
    upload_to_qdrant(chunks, embeddings, metadatas, collection_name, file_hash)

@log_call
def vectordb_upload_files(org_code: str, file_paths: list[str], collection_name: str):
    file_hashes = []
    client = QdrantClient(
        url=os.getenv("QDRANT_URL")
    )
    
    collections = client.get_collections()

    for file_path in file_paths:
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        
        if collection_name in [c.name for c in collections.collections]:
            points, _ = client.scroll(
                collection_name=collection_name,
                scroll_filter={"must": [{"key": "file_hash", "match": {"value": file_hash}}]},
                limit=1
            )
            if points:
                pass
            else:
                process_and_upload(file_path, collection_name, file_hash)
        else:
            process_and_upload(file_path, collection_name, file_hash)
        
        file_info = {
            "filename": os.path.basename(file_path),
            "file_hash": file_hash,
            "file_size": os.path.getsize(file_path),
            "uploaded_at": datetime.datetime.now(KST)
        }
        mdb.add_vectorstore(org_code, collection_name, files=[file_info])
        file_hashes.append(file_hash)
    
    return file_hashes

@log_call
def delete_collection(collection_name: str):
    client = QdrantClient(
        url=os.getenv("QDRANT_URL")
    )
    client.delete_collection(collection_name=collection_name)

@log_call
def delete_points_by_file_hash(collection_name: str, file_hash: str):
    client = QdrantClient(
        url=os.getenv("QDRANT_URL")
    )

    points, _ = client.scroll(
        collection_name=collection_name,
        scroll_filter={"must": [{"key": "file_hash", "match": {"value": file_hash}}]},
        limit=1000
    )

    ids = [p.id for p in points]
    if ids:
        client.delete(collection_name=collection_name, points_selector={"points": ids})
        logger.info(f"🗑️ 삭제 완료: {len(ids)}개 포인트 (file_hash: {file_hash})")
    else:
        logger.info(f"ℹ️ 삭제할 포인트 없음 (file_hash: {file_hash})")

@log_call
def clone_collection(source_collection: str, target_collection: str, batch_size: int = 500):
    client = QdrantClient(url=os.getenv("QDRANT_URL"))

    cols = client.get_collections().collections
    src_info = next((c for c in cols if c.name == source_collection), None)
    if src_info is None:
        raise ValueError(f"원본 컬렉션 '{source_collection}'을 찾을 수 없습니다.")

    if any(c.name == target_collection for c in cols):
        client.delete_collection(collection_name=target_collection)

    vparams = VectorParams(
        size=src_info.vectors.vector_size,
        distance=Distance(src_info.vectors.distance)
    )
    client.recreate_collection(
        collection_name=target_collection,
        vectors_config=vparams
    )

    offset = None
    while True:
        points, next_page = client.scroll(
            collection_name=source_collection,
            limit=batch_size,
            offset=offset
        )
        if not points:
            break

        to_insert = [
            PointStruct(id=p.id, vector=p.vector, payload=p.payload)
            for p in points
        ]
        client.upsert(
            collection_name=target_collection,
            points=to_insert
        )
        if not next_page:
            break
        offset = next_page

    logger.info(f"✅ '{source_collection}' → '{target_collection}' 복제 완료")


# ==== CSV Ingestion: Course Metadata ====

class CourseMetadata(BaseModel):
    course_id: str = Field(..., description="Unique course identifier")
    course_name: str
    course_description: str
    product_family: Optional[str] = None
    category: Optional[str] = None
    difficulty: Optional[str] = None
    keywords: Optional[str] = None
    estimated_time_minutes: Optional[str] = None
    prerequisite_courses: Optional[str] = None
    related_courses: Optional[str] = None
    created_date: Optional[str] = None
    Link: Optional[str] = None

    def as_search_text(self) -> str:
        parts = [
            f"{self.course_name}",
            f"{self.course_description}",
            f"제품군: {self.product_family or ''}",
            f"카테고리: {self.category or ''}",
            f"난이도: {self.difficulty or ''}",
            f"키워드: {self.keywords or ''}",
        ]
        return "\n".join(p for p in parts if p)


@log_call
def ingest_courses_csv(file_path: str, collection_name: str, org_code: Optional[str] = None) -> str:
    """Read a CSV of course metadata, embed each row, and upsert to Qdrant.

    Returns the computed file hash used to tag points.
    """
    # Compute file hash for traceability / idempotency
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    # Parse CSV (handle BOM with utf-8-sig)
    rows: List[CourseMetadata] = []
    with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            # Normalize keys just in case of hidden BOM on header
            normalized = { (k or "").strip(): (v or "").strip() for k, v in raw.items() }
            # Map common header variants
            model = CourseMetadata(**normalized)
            rows.append(model)

    # Build chunks and payload metadata
    chunks: List[str] = []
    metas: List[Dict] = []
    for idx, row in enumerate(rows, start=1):
        chunks.append(row.as_search_text())
        metas.append({
            "row": idx,
            "course_id": row.course_id,
            "course_name": row.course_name,
            "course_description": row.course_description,
            "product_family": row.product_family,
            "category": row.category,
            "difficulty": row.difficulty,
            "keywords": row.keywords,
            "estimated_time_minutes": row.estimated_time_minutes,
            "prerequisite_courses": row.prerequisite_courses,
            "related_courses": row.related_courses,
            "created_date": row.created_date,
            "link": row.Link,
        })

    # Embed and upload
    vectors = embed_texts(chunks)
    upload_to_qdrant(chunks, vectors, metas, collection_name, file_hash)

    # Optional: register vectorstore file reference in Mongo if org_code provided
    if org_code:
        try:
            file_info = {
                "filename": os.path.basename(file_path),
                "file_hash": file_hash,
                "file_size": os.path.getsize(file_path),
                "uploaded_at": datetime.datetime.now(KST)
            }
            # Check if add_vectorstore method exists
            if hasattr(mdb, 'add_vectorstore'):
                mdb.add_vectorstore(org_code, collection_name, files=[file_info])
            else:
                logger.warning(f"MongoDB vectorstore registration skipped: add_vectorstore method not available")
        except Exception as e:
            logger.error(f"MongoDB vectorstore registration failed: {e}", exc_info=True)

    return file_hash


@log_call
def search_qdrant(query: str, collection_name: str, top_k: int = 5) -> List[Dict]:
    """Semantic search over a Qdrant collection using the embedding model.

    Returns a list of dicts with id, score, and payload.
    """
    client = QdrantClient(url=os.getenv("QDRANT_URL"))
    qvec = embed_query(query)
    results = client.search(
        collection_name=collection_name,
        query_vector=qvec,
        limit=top_k,
        with_payload=True
    )
    return [
        {"id": r.id, "score": r.score, "payload": r.payload}
        for r in results
    ]
