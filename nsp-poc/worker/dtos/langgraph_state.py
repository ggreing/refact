from typing import List, Optional, Dict, Any, Callable, Awaitable
from typing_extensions import TypedDict




class Langgraph_State(TypedDict, total=False):
    query: Optional[str]                                    # 사용자 입력 쿼리
    memory: Optional[List[Any]]                             # 대화 히스토리
    vectorstore: Optional[List[str]]                        # 벡터 스토어 ids
    file_search: Optional[List[str]]                        # 파일 검색 결과
    result: Optional[str]                                   # graph 결과
    metadata: Optional[Dict[str, Any]]                      # 추가 메타데이터 (user_id, thread_id, message_id 등)
    model: Optional[str]                                    # LLM 모델명
    stream_sender: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]]  # 스트리밍 큐 전송 함수
    next_step: Optional[str]                                # 슈퍼바이저가 결정한 다음 스텝
    supervisor_reasoning: Optional[str]                     # 슈퍼바이저 추론 과정
    # 코스 추천 서브플로우에서 사용하는 필드들 (메인 State에 통합)
    requirements: Optional[Dict[str, Any]]                  # 요구사항 분석 결과
    retrieved_courses: Optional[List[Any]]   # 검색된 코스 목록
    recommendation: Optional[Dict[str, Any]]                # 최종 추천 결과
    guardrail: Any
    # 추가 확장 필드 (통합 State 전용)
    reasoning: Optional[str]                                # 노드 실행 중 추론 텍스트
    error: Optional[str]                                    # 에러 메시지 저장
    answer: Optional[str]                                   # 일반 chat / rubicon 답변
