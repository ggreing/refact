import os
from langchain.text_splitter import TokenTextSplitter
from .utils import log_call, get_chunk_line_number

@log_call
def load_file(file_path: str) -> list[dict]:
    file_name = os.path.basename(file_path)
    
    if file_name.endswith('.pdf'):
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            pages.append({
                "page": i + 1,
                "text": text,
                "source_type": "pdf",
            })
        return pages
    elif file_name.endswith('.txt'):
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        return [{"page": 1, "text": text, "source_type": "txt"}]
    elif file_name.endswith('.docx'):
        import docx
        doc = docx.Document(file_path)
        text = "\n".join([p.text for p in doc.paragraphs])
        return [{"page": 1, "text": text, "source_type": "docx"}]
    else:
        raise ValueError("지원하지 않는 파일 형식입니다.")

@log_call
def chunk_text_with_metadata(docs: list[dict], chunk_size: int = 500, chunk_overlap: int = 50) -> tuple[list[str], list[dict]]:
    splitter = TokenTextSplitter(
        encoding_name="cl100k_base",
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    all_chunks = []
    all_metadata = []
    for doc in docs:
        chunks = splitter.split_text(doc["text"])
        if doc["source_type"] == "pdf":
            for chunk in chunks:
                meta = {
                    "page": doc["page"],
                }
                all_chunks.append(chunk)
                all_metadata.append(meta)
        else:
            for chunk in chunks:
                line_num = get_chunk_line_number(doc["text"], chunk)
                meta = {
                    "line": line_num,
                }
                all_chunks.append(chunk)
                all_metadata.append(meta)
    return all_chunks, all_metadata