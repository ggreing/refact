"""
LangGraph와 Langfuse 통합을 위한 커스텀 핸들러 모듈

이 모듈은 LangGraph와 pydantic_ai의 트레이스를 Langfuse에서 통합하여 
보여주기 위한 커스텀 핸들러와 유틸리티 함수들을 제공합니다.
"""

from functools import wraps
from typing import Any, Dict
import inspect
from langchain_core.runnables import RunnableConfig
from langfuse.langchain import CallbackHandler
from opentelemetry.sdk.trace import Span


class CustomLangfuseHandler(CallbackHandler):
    """LangGraph 체크포인트 네임스페이스별로 run_id를 저장하는 커스텀 Langfuse 핸들러
    
    이 핸들러는 LangGraph의 각 체크포인트 네임스페이스와 run_id를 매핑하여
    저장함으로써 나중에 트레이스 컨텍스트를 올바르게 연결할 수 있도록 합니다.
    """

    ns_to_run_id: Dict[str, str] = {}

    def on_chain_start(self, *args, **kwargs):
        """LangGraph 체크포인트 네임스페이스별로 run_id를 저장
        
        체인이 시작될 때 호출되어 체크포인트 네임스페이스와 run_id를
        매핑하여 저장합니다.
        """
        langgraph_checkpoint_ns = kwargs["metadata"].get("langgraph_checkpoint_ns")

        if langgraph_checkpoint_ns:
            self.ns_to_run_id[langgraph_checkpoint_ns] = kwargs["run_id"]
        super().on_chain_start(*args, **kwargs)

    def on_chain_error(self, error: Exception, **kwargs: Any) -> None:
        """LangGraph 체인 실행 중 에러 발생 시 호출됩니다.
        
        에러 정보를 로깅하고 Langfuse에 전송합니다.
        """
        print(f"LangGraph chain error: {error}")
        super().on_chain_error(error, **kwargs)


def get_langfuse_handler(config: RunnableConfig) -> CustomLangfuseHandler:
    """LangGraph 설정에서 Langfuse 핸들러를 가져오기
    
    매개변수
    -------
    config : RunnableConfig
        LangGraph 실행 설정
        
    반환값
    -----
    CustomLangfuseHandler
        설정에서 찾은 커스텀 Langfuse 핸들러
    """
    callback_handlers = config["callbacks"].handlers
    langfuse_handler = next(
        (
            callback
            for callback in callback_handlers
            if isinstance(callback, CustomLangfuseHandler)
        ),
        None,
    )
    return langfuse_handler


def get_langfuse_span(config: RunnableConfig) -> Span | None:
    """설정에서 Langfuse span을 가져오기
    
    체크포인트 네임스페이스에 해당하는 Langfuse span을 반환합니다.
    
    매개변수
    -------
    config : RunnableConfig
        LangGraph 실행 설정
        
    반환값
    -----
    Span | None
        해당하는 OpenTelemetry span 또는 None
    """
    langgraph_checkpoint_ns = config["metadata"]["langgraph_checkpoint_ns"]
    langfuse_handler = get_langfuse_handler(config)

    if (
        not langfuse_handler
        or langfuse_handler.ns_to_run_id.get(langgraph_checkpoint_ns, None) is None
    ):
        return None  # 연결할 span이 없음

    return langfuse_handler.runs[
        langfuse_handler.ns_to_run_id[langgraph_checkpoint_ns]
    ].start_as_current_span(name="pydantic AI")


def spread_context(func):
    """LangGraph 노드 내부로 Langfuse 컨텍스트를 전파하는 데코레이터
    
    이 데코레이터는 LangGraph 노드 함수를 감싸서 Langfuse의 트레이싱
    컨텍스트를 노드 내부로 전파합니다. 이를 통해 pydantic_ai 등의
    다른 라이브러리에서 생성되는 트레이스가 올바른 부모 트레이스
    하위에 중첩되도록 할 수 있습니다.

    매개변수
    -------
    func : Callable
        컨텍스트 전파로 래핑할 LangGraph 노드 함수
        함수 시그니처는 (state, config, *args, **kwargs)여야 함

    반환값
    -----
    Callable
        컨텍스트 전파를 포함한 래핑된 함수
        
    사용 예시
    -------
    @spread_context
    def my_node(state: State, config: RunnableConfig):
        # 이 노드 내부에서 실행되는 모든 트레이싱이
        # LangGraph 트레이스 하위에 중첩됩니다
        return {"result": "some_result"}
    """

    @wraps(func)
    def sync_wrapper(state: Any, config: RunnableConfig, *args, **kwargs):
        span = get_langfuse_span(config)

        if span:
            with span:
                return func(state, config, *args, **kwargs)
        else:
            return func(state, config, *args, **kwargs)

    @wraps(func)
    async def async_wrapper(state: Any, config: RunnableConfig, *args, **kwargs):
        span = get_langfuse_span(config)

        if span:
            with span:
                result = func(state, config, *args, **kwargs)
                if inspect.isawaitable(result):
                    return await result
                return result
        else:
            result = func(state, config, *args, **kwargs)
            if inspect.isawaitable(result):
                return await result
            return result

    return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper


def get_custom_langfuse_handler():
    """커스텀 Langfuse 핸들러 초기화 함수
    
    환경변수에서 Langfuse 설정을 읽어와 CustomLangfuseHandler 인스턴스를 반환합니다.
    환경변수 LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST가 
    미리 설정되어 있어야 합니다.
    
    반환값
    -----
    CustomLangfuseHandler
        초기화된 커스텀 Langfuse 핸들러
        
    사용 예시
    -------
    # 환경변수를 미리 설정한 후 사용
    handler = get_custom_langfuse_handler()
    # LangGraph에서 사용
    result = graph.astream(state, config={"callbacks": [handler]})
    """
    return CustomLangfuseHandler()