from shared.utils import log_call  # 공용화된 유틸 사용
import logging
import os
from functools import wraps

os.makedirs('log', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='log/qdrant_log.log',
    filemode='a'
)


def get_chunk_line_number(original_text: str, chunk: str) -> int:
    lines = original_text.splitlines(keepends=True)
    positions = []
    offset = 0
    for line in lines:
        positions.append(offset)
        offset += len(line)
    
    snippet = chunk[:30]
    chunk_offset = original_text.find(snippet)
    
    line_number = None
    for i, pos in enumerate(positions):
        if chunk_offset < pos:
            line_number = i - 1 if i > 0 else 0
            break
    if line_number is None:
        line_number = len(positions) - 1
    
    return line_number + 1