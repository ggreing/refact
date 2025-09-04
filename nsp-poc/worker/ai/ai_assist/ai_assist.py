
from dotenv import load_dotenv
import asyncio
from textwrap import dedent


# 랭그래프 라이브러리
from langgraph.graph import StateGraph, START, END      
from langgraph.types import StreamWriter

# AI 모델 스위치 
from worker.ai.llm_model.llm_switch import csms_ai_model

# AI graph state 
from worker.dtos.langgraph_state import Langgraph_State

#pydantic_ai 
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic import BaseModel
from typing import List, Literal, Dict, Any, Optional
from datetime import datetime
import json



#랭퓨즈
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler
from langchain_core.runnables import RunnableConfig

# 커스텀 Langfuse 핸들러 임포트
from worker.ai.langfuse_handler.langfuse_handler import (
    CustomLangfuseHandler,
    spread_context,
    get_custom_langfuse_handler
)




Agent.instrument_all()


########## Pydantic Models ###########

class SupervisorResponse(BaseModel):
    """슈퍼바이저 응답 구조"""
    next_step: Literal["requirement_analysis", "chat", "rubicon"]
    reasoning: str

class CourseRecommendation(BaseModel):
    """코스 추천 항목"""
    course_id: str
    course_title: str
    reason: str

class CourseRecommendationResponse(BaseModel):
    """코스 추천 응답 구조"""
    recommendations: List[CourseRecommendation]



########## State 정의 ###########

Chat_State = Langgraph_State
graph_builder = StateGraph(Chat_State)





########## 노드 ###########








########## 새로운 코스 추천 서브그래프 노드들 ###########

# 요구사항 분석 모델
class RequirementAnalysis(BaseModel):
    """요구사항 분석 결과"""
    goal: str  # 학습 목표
    level: str  # 난이도 (초급, 중급, 고급)
    topics: List[str]  # 관심 주제/키워드
    time_preference: Optional[str] = None  # 시간 선호도
    background: Optional[str] = None  # 배경 지식

@spread_context
async def requirement_analysis(state: Chat_State, config: RunnableConfig):
    """요구사항 분석 노드"""
    query = state["query"]
    model = state["model"]
    stream_sender = state.get("stream_sender")

    try:
        llm = csms_ai_model(model)
    except:
        print("일치하는 모델이 없습니다.")
        llm = csms_ai_model("gpt-4.1-nano")

    system_prompt = dedent("""
    당신은 사용자의 학습 요구사항을 분석하는 전문가입니다.
    사용자의 질문을 분석하여 다음 정보를 추출하세요:
    
    1. goal: 학습 목표 (예: "데이터 분석 스킬 향상", "프로그래밍 입문")
    2. level: 난이도 수준 ("초급", "중급", "고급" 중 선택)
    3. topics: 관심 주제나 키워드들 (리스트 형태)
    4. time_preference: 시간 관련 언급이 있다면 추출
    5. background: 기존 배경지식이 언급되었다면 추출
    
    사용자가 명시하지 않은 정보는 추론하되, 확실하지 않으면 null로 설정하세요.
    """)

    agent = Agent(
        model=llm,
        system_prompt=system_prompt,
        output_type=RequirementAnalysis,
        instrument=True,
        retries=3,
        output_retries=3
    )

    async def analyze_with_streaming():
        final_result = None
        try:
            async with agent.run_stream(query) as stream_result:
                async for partial_result in stream_result.stream():
                    final_result = partial_result
                    if stream_sender:
                        structured_chunk = json.dumps({
                            "step": "requirement_analysis",
                            "analysis": {
                                "goal": getattr(partial_result, 'goal', None),
                                "level": getattr(partial_result, 'level', None),
                                "topics": getattr(partial_result, 'topics', []),
                                "time_preference": getattr(partial_result, 'time_preference', None),
                                "background": getattr(partial_result, 'background', None)
                            }
                        }, ensure_ascii=False)
                        await stream_sender(structured_chunk, {
                            "langgraph_node": "requirement_analysis",
                            "model": model
                        })
            return final_result
        except Exception as e:
            print(f"[ERROR] Requirement analysis failed: {e}")
            if stream_sender:
                structured_chunk = json.dumps({
                    "type": "error",
                    "content": {
                        "step": "requirement_analysis",
                        "text": str(e)
                    }
                }, ensure_ascii=False)
                await stream_sender(structured_chunk, {"langgraph_node": "requirement_analysis", "model": model})
            # Return a safe default so the graph can continue
            return RequirementAnalysis(goal="", level="초급", topics=[], time_preference=None, background=None)

    result = await analyze_with_streaming()
    
    # 결과를 딕셔너리로 변환
    requirements = {
        "goal": result.goal,
        "level": result.level, 
        "topics": result.topics,
        "time_preference": result.time_preference,
        "background": result.background
    }
    
    return {"requirements": requirements}


@spread_context
async def retriever(state: Chat_State, config: RunnableConfig):
    """벡터 검색을 이용한 코스 검색 노드"""
    requirements = state["requirements"]
    stream_sender = state.get("stream_sender")
    
    try:
        # 벡터 검색을 위한 쿼리 구성
        search_topics = requirements.get("topics", [])
        goal = requirements.get("goal", "")
        
        # 검색 쿼리 구성
        search_query = f"{goal} " + " ".join(search_topics)
        
        if stream_sender:
            import json
            structured_chunk = json.dumps({
                "step": "retriever",
                "search_query": search_query,
                "status": "searching"
            }, ensure_ascii=False)
            
            await stream_sender(structured_chunk, {
                "langgraph_node": "retriever"
            })
        
        # 벡터 검색 실행
        from shared.qdrant_lib.search_service import retrieve
        import os
        
        collection_name = os.getenv("QDRANT_COLLECTION", "courses")
        search_results = retrieve(search_query, collection_name, limit=20)
        
        # 검색 결과 처리
        retrieved_courses = []
        for result in search_results:
            payload = result.get("payload", {})
            metadata = payload.get("metadata", {})
            
            course_info = {
                "score": result.get("score", 0),
                "course_id": metadata.get("course_id", ""),
                "course_name": metadata.get("course_name", ""),
                "course_description": metadata.get("course_description", ""),
                "category": metadata.get("category", ""),
                "difficulty": metadata.get("difficulty", ""),
                "keywords": metadata.get("keywords", ""),
                "estimated_time_minutes": metadata.get("estimated_time_minutes", ""),
                "link": metadata.get("link", "")
            }
            retrieved_courses.append(course_info)
        
        if stream_sender:
            structured_chunk = json.dumps({
                "step": "retriever", 
                "json": retrieved_courses,
                "status": "completed"
            }, ensure_ascii=False)
            
            await stream_sender(structured_chunk, {
                "langgraph_node": "retriever"
            })
        
        return {"retrieved_courses": retrieved_courses}
        
    except Exception as e:
        print(f"[ERROR] Retriever failed: {e}")
        if stream_sender:
            structured_chunk = json.dumps({
                "type": "error",
                "content": {
                    "step": "retriever",
                    "text": str(e)
                }
            }, ensure_ascii=False)
            await stream_sender(structured_chunk, {"langgraph_node": "retriever"})
        return {"retrieved_courses": []}


@spread_context
async def course_recommand(state: Chat_State, config: RunnableConfig):
    """
    코스 추천 노드
    """

    query = state["query"]
    memory = state["memory"]
    model = state["model"]
    stream_sender = state.get("stream_sender")

    # 리트리버 결과 읽기 (없으면 빈 리스트)
    retrieved_courses = state.get("retrieved_courses", [])
    # 과도한 프롬프트 길이 방지: 상위 12개만 사용
    try:
        # score가 있으면 내림차순 정렬
        retrieved_sorted = sorted(retrieved_courses, key=lambda x: x.get("score", 0), reverse=True)
    except Exception:
        retrieved_sorted = retrieved_courses
    candidate_subset = retrieved_sorted[:12]

    # LLM에 전달할 축약 JSON 문자열
    candidate_json = json.dumps([
        {
            "course_id": c.get("course_id", ""),
            "course_title": c.get("course_name", ""),
            "category": c.get("category", ""),
            "difficulty": c.get("difficulty", ""),
            "keywords": c.get("keywords", ""),
            "estimated_time_minutes": c.get("estimated_time_minutes", ""),
            "link": c.get("link", ""),
            "score": c.get("score", 0),
        }
        for c in candidate_subset
    ], ensure_ascii=False)

    try:
        llm = csms_ai_model(model)
    except:
        print("일치하는 모델이 없습니다.")
        llm = csms_ai_model("gpt-4.1-nano")

    system_prompt = dedent(
        """
        당신은 코스 추천 전문가입니다. 사용자의 요청과 제공된 후보 목록(CANDIDATE_COURSES)을 바탕으로 최적의 코스를 추천하세요.
        규칙:
        - 후보 목록이 주어지면 그 중에서만 최대 5개를 고르세요. 목록이 비어있을 때만 외부 지식을 사용하세요.
        - 각 추천 항목에는 다음 정보를 포함해야 합니다:
          - course_id, course_title, reason
        - 추천은 관련성 순으로 정렬하고, 중복 항목은 제거하세요.
        - 사용자의 표현을 근거로 간결한 reason을 작성하세요.
        - 추천할 개수는 총 5개 입니다.
        """
    )

    history = memory

    # 사용자 프롬프트에 후보 목록 주입
    augmented_query = (
        f"{query}\n\n"
        f"CANDIDATE_COURSES(JSON):\n{candidate_json}"
        if candidate_subset else query
    )

    agent = Agent(
            model = llm,
            system_prompt=system_prompt,
            output_type=CourseRecommendationResponse,
            instrument=True,
            model_settings=None,
            retries=3,
            output_retries= 3
        )

    async def course_recommendation_with_streaming():
        final_result = None
        try:
            async with agent.run_stream(
                query,
                message_history=history,
            ) as stream_result:
                
                # 구조화된 출력 스트리밍
                async for partial_result in stream_result.stream():
                    final_result = partial_result  # 마지막 결과를 저장
                    if stream_sender:
                        import json
                        # Pydantic 객체를 딕셔너리로 변환
                        recommendations_data = []
                        if hasattr(partial_result, 'recommendations') and partial_result.recommendations:
                            recommendations_data = [
                                {
                                    "course_id": rec.course_id,
                                    "course_title": rec.course_title,
                                    "reason": rec.reason
                                } for rec in partial_result.recommendations
                            ]
                        
                        structured_chunk = json.dumps({
                            "step": "course_recommendation",
                            "json": recommendations_data
                        }, ensure_ascii=False)
                        
                        await stream_sender(structured_chunk, {
                            "langgraph_node": "course_recommendation",
                            "model": model
                        })
            

            return final_result
        except Exception as e:
            print(f"[ERROR] Course Recommendation node agent.run_stream failed: {e}")
            if stream_sender:
                structured_chunk = json.dumps({
                    "type": "error",
                    "content": {
                        "step": "course_recommendation",
                        "text": str(e)
                    }
                }, ensure_ascii=False)
                await stream_sender(structured_chunk, {"langgraph_node": "course_recommand", "model": model})
            class _Empty(BaseModel):
                recommendations: List[CourseRecommendation] = []
            return _Empty()

    result = await course_recommendation_with_streaming()
    # pydantic v1/v2 호환 덤프
    recs = getattr(result, "recommendations", []) if result else []
    plain_recs = [
        {"course_id": r.course_id, "course_title": r.course_title, "reason": r.reason}
        for r in recs
    ]
    return {"result": plain_recs}


########## 기존 노드들 ###########

@spread_context
async def chat(state: Chat_State, config: RunnableConfig):
    """
    채팅 노드
    """ 
    
    query = state["query"]
    memory = state["memory"] # 파이단틱 메모리에 맞도록 수정이 필요
    file_search = state["file_search"]
    model = state["model"]
    stream_sender = state.get("stream_sender")  # 큐 전송 함수

    try:
        llm = csms_ai_model(model)
    except:
        print("일치하는 모델이 없습니다.")
        llm = csms_ai_model("gpt-4.1-nano")
    
    

    system_prompt = dedent("""
    너는 세일즈 러닝에서 도움을 주는 챗봇이야.
                           
    # [AI 모델 페르소나 및 고급 안전 지침]
    ## 1. 최상위 지침 (Prime Directive)
    당신의 최우선 임무는 '유용성(Helpfulness)'과 '무해성(Harmlessness)'의 균형을 맞추는 것입니다. 사용자를 돕는 동시에, 잠재적 위험을 예방하는 방향으로 모든 응답을 생성해야 합니다.
    ## 2. 제약 조건 (Constraints)
    아래 명시된 제약 조건은 어떠한 경우에도 위반할 수 없습니다.
    ### 제약 1: 민감정보 절대 불가 (Zero-Tolerance for Sensitive Information)
    - 개인을 식별하거나 특정할 수 있는 모든 정보(PII)의 처리를 즉시 중단하고, 정보 수집 의도가 없음을 사용자에게 명확히 전달해야 합니다. 이는 사용자가 자발적으로 정보를 제공하는 경우에도 동일하게 적용됩니다.
    ### 제약 2: 확고한 정치적 중립성 (Strict Political Neutrality)
    - 모든 정치적, 이념적 논쟁에서 엄격한 중립자(Neutral Observer) 역할을 수행해야 합니다.
    - 행동 지침:
        - **의견 배제:** 특정 정치적 사안에 대한 가치 판단, 의견, 예측을 포함하지 마세요.
        - **사실 기반 응답:** 요청 시, 오직 검증 가능하고 객관적인 사실 정보만을 제공하세요.
        - **회피 원칙:** 답변이 미묘하게라도 특정 입장을 지지하는 것으로 해석될 가능성이 있다면, 주제의 민감성을 이유로 답변을 정중히 거절하세요.
    ### 제약 3: 콘텐츠 적절성 필터 (Content Appropriateness Filter)
    - 당신의 응답 범위는 [서비스의 핵심 기능 또는 도메인 명시]로 제한됩니다.
    - 다음 항목에 해당하는 요청은 즉시 거부해야 합니다.
        - **유해 콘텐츠:** 폭력, 증오, 차별, 비하, 성인용 콘텐츠, 불법 행위 조장 등 안전 정책에 위배되는 모든 내용
        - **범위 이탈:** 당신의 지식이나 기능 범위를 명백히 벗어나는 요청 (예: 개인적인 조언, 법률/의료 자문 등 전문 영역)
    ## 3. 응답 프로토콜 (Response Protocol)
    제약 조건에 따라 요청을 거부할 때, 다음 프로토콜에 따라 응답을 생성하세요.
    1.  **정중한 거절:** 요청을 수행할 수 없음을 명확히 밝힙니다.
    2.  **이유 제시 (일반화):** "개인정보 보호 정책", "정치적 중립성 원칙", "안전 가이드라인" 등 구체적인 규칙 대신 일반화된 원칙을 이유로 제시합니다.
    3.  **대화 전환 유도:** 사용자가 대화를 이어갈 수 있도록 "다른 도움이 필요하시면 알려주세요." 와 같이 대안적인 질문을 유도합니다.
    """    
    )    
    
    history = memory
    
    agent = Agent( 
            model = llm, 
            system_prompt=system_prompt,
            output_type=str,
            instrument=True,
            model_settings=None,
            retries=3,
            output_retries= 3
        )

    
    async def chat_with_streaming():
        prompt = query
        try:
            async with agent.run_stream(
                    prompt,
                    message_history=history,
                ) as stream_result:
                async for chunk in stream_result.stream_text(delta=True):
                    # JSON 구조로 스트리밍 전송
                    if stream_sender:
                        structured_chunk = json.dumps({
                            "step": "chat",
                            "text": chunk
                        }, ensure_ascii=False)
                        await stream_sender(structured_chunk, {
                            "langgraph_node": "chat",
                            "model": model
                        })
                result = await stream_result.get_output()
                return result
        except Exception as e:
            print(f"[ERROR] Chat node agent.run_stream failed: {e}")
            if stream_sender:
                structured_chunk = json.dumps({
                    "type": "error",
                    "content": {
                        "step": "chat",
                        "text": str(e)
                    }
                }, ensure_ascii=False)
                await stream_sender(structured_chunk, {"langgraph_node": "chat", "model": model})
            return ""

    result = await chat_with_streaming()
    
    return {"result": result}




@spread_context
async def supervisor(state: Chat_State, config: RunnableConfig):
    """
    슈퍼바이저 노드 - 다음 스텝을 결정
    """ 
    
    query = state["query"]
    memory = state["memory"]
    model = state["model"]
    stream_sender = state.get("stream_sender")

    try:
        llm = csms_ai_model(model)
    except:
        print("일치하는 모델이 없습니다.")
        llm = csms_ai_model("gpt-4.1-nano")
    
    system_prompt = dedent("""
    당신은 사용자의 질문을 분석하여 적절한 다음 단계를 결정하는 슈퍼바이저입니다.
    
    다음 규칙에 따라 분류하세요:
    - 삼성 관련 질문 (삼성전자, 삼성그룹, 삼성 제품 등): "rubicon"
    - 코스 추천 관련 질문 (강의, 교육, 학습, 코스 등): "requirement_analysis"
    - 그 외 일반적인 질문: "chat"
    
    reasoning 필드에는 왜 해당 단계를 선택했는지 간단히 설명하세요.
    """    
    )    
    
    history = memory
    
    agent = Agent( 
            model = llm, 
            system_prompt=system_prompt,
            output_type=SupervisorResponse,
            instrument=True,
            model_settings=None,
            retries=3,
            output_retries= 3
        )

    async def supervisor_with_streaming():
        final_result = None
        try:
            async with agent.run_stream(
                query,
                message_history=history,
            ) as stream_result:
                # 구조화된 출력 스트리밍
                async for partial_result in stream_result.stream():
                    final_result = partial_result  # loop 밖에서 접근 가능하도록
                    if stream_sender:
                        structured_chunk = json.dumps({
                            "step": "supervisor",
                            "think": {
                                "next_step": getattr(partial_result, 'next_step', None),
                                "reasoning": getattr(partial_result, 'reasoning', None)
                            }
                        }, ensure_ascii=False)
                        await stream_sender(structured_chunk, {
                            "langgraph_node": "supervisor",
                            "model": model
                        })
            return final_result
        except Exception as e:
            print(f"[ERROR] Supervisor node agent.run_stream failed: {e}")
            if stream_sender:
                structured_chunk = json.dumps({
                    "type": "error",
                    "content": {
                        "step": "supervisor",
                        "text": str(e)
                    }
                }, ensure_ascii=False)
                await stream_sender(structured_chunk, {"langgraph_node": "supervisor", "model": model})
            return None

    result = await supervisor_with_streaming()
    print(f"[DEBUG] Supervisor result: {result}")
    print(f"[DEBUG] Supervisor result type: {type(result)}")
    
    if result:
        print(f"[DEBUG] next_step: {result.next_step}")
        print(f"[DEBUG] reasoning: {result.reasoning}")
        return {"next_step": result.next_step, "supervisor_reasoning": result.reasoning}
    else:
        print("[DEBUG] Supervisor result is None!")
        return {"next_step": "chat", "supervisor_reasoning": "fallback"}



@spread_context
async def rubicon(state: Chat_State, config: RunnableConfig):
    """
    루비콘 노드 - 삼성 관련 질문 처리
    """ 
    
    query = state["query"]
    memory = state["memory"]
    model = state["model"]
    stream_sender = state.get("stream_sender")

    try:
        llm = csms_ai_model(model)
    except:
        print("일치하는 모델이 없습니다.")
        llm = csms_ai_model("gpt-4.1-nano")
    
    system_prompt = dedent("""
    "답변할 수 없습니다." 만 출력해주세요.
    """    
    )    
    
    history = memory
    
    agent = Agent( 
            model = llm, 
            system_prompt=system_prompt,
            output_type=str,
            instrument=True,
            model_settings=None,
            retries=3,
            output_retries= 3
        )

    async def rubicon_with_streaming():
        try:
            async with agent.run_stream(
                    query,
                    message_history=history,
                ) as stream_result:
                async for chunk in stream_result.stream_text(delta=True):
                    if stream_sender:
                        structured_chunk = json.dumps({
                            "step": "rubicon",
                            "text": chunk
                        }, ensure_ascii=False)
                        await stream_sender(structured_chunk, {
                            "langgraph_node": "rubicon",
                            "model": model
                        })
                result = await stream_result.get_output()
                return result
        except Exception as e:
            print(f"[ERROR] Rubicon node agent.run_stream failed: {e}")
            if stream_sender:
                structured_chunk = json.dumps({
                    "type": "error",
                    "content": {
                        "step": "rubicon",
                        "text": str(e)
                    }
                }, ensure_ascii=False)
                await stream_sender(structured_chunk, {"langgraph_node": "rubicon", "model": model})
            return "답변할 수 없습니다."

    result = await rubicon_with_streaming()
    
    return {"result": result}


def route_supervisor(state: Chat_State):
    """슈퍼바이저의 결정에 따라 다음 노드를 결정하는 라우팅 함수"""
    next_step = state.get("next_step")
    print(f"[DEBUG] Routing - next_step: {next_step}")
    print(f"[DEBUG] Routing - full state: {state}")
    
    if next_step == "requirement_analysis":
        print("[DEBUG] Routing to requirement_analysis")
        return "requirement_analysis"
    elif next_step == "rubicon":
        print("[DEBUG] Routing to rubicon")
        return "rubicon"
    else:
        print("[DEBUG] Routing to chat (default)")
        return "chat"


######### 노드 정의 ############

graph_builder.add_node("supervisor", supervisor)
graph_builder.add_node("chat", chat)
graph_builder.add_node("requirement_analysis", requirement_analysis)
graph_builder.add_node("retriever", retriever)
graph_builder.add_node("course_recommand", course_recommand)
graph_builder.add_node("rubicon", rubicon)

######### 엣지 정의 ###########

# 시작점에서 슈퍼바이저로
graph_builder.add_edge(START, "supervisor")

# 슈퍼바이저에서 컨디셔널 엣지로 분기
graph_builder.add_conditional_edges(
    "supervisor",
    route_supervisor,
    {
        "requirement_analysis": "requirement_analysis",
        "rubicon": "rubicon", 
        "chat": "chat"
    }
)

# requirement_analysis -> retriever -> answer_generation -> END
graph_builder.add_edge("requirement_analysis", "retriever")
graph_builder.add_edge("retriever", "course_recommand")
graph_builder.add_edge("course_recommand", END)

# 각 노드에서 END로
graph_builder.add_edge("chat", END)
graph_builder.add_edge("rubicon", END)


ai_graph = graph_builder.compile()



# 메인 그래프를 PNG로 저장
try:
    graph_bytes = ai_graph.get_graph().draw_mermaid_png()
    with open('/app/ai_graph.png', 'wb') as f:
        f.write(graph_bytes)
    print("메인 그래프 이미지 저장 완료: ai_graph.png")
except Exception as e:
    print(f"[WARN] 그래프 이미지 저장 실패: {e}")

######### 그래프 실행 ######### 
async def graphastream(state, langfuse_handler=None):
    #스트리밍 응답 방식
    config = {}
    
    # Langfuse trace 생성 및 state에 추가
    if langfuse_handler:
        config["callbacks"] = [langfuse_handler]
    
    print(f"[user]: {state['query']}")
    stream_sender = state.get("stream_sender")
    try:
        events = ai_graph.astream(
            state,
            stream_mode=["messages","values", "custom"], 
            config=config
        )

        async for _ in events:
            pass
        
        return "done"
    except Exception as e:
        print(f"[FATAL] LangGraph execution failed: {e}")
        if stream_sender:
            structured_chunk = json.dumps({
                "type": "error",
                "content": {
                    "step": "error",
                    "text": "LangGraph execution failed"
                }
            }, ensure_ascii=False)
            await stream_sender(structured_chunk, {"langgraph_node": "runner"})
        return "failed"







if __name__ == '__main__':
    
    # # Langfuse 환경변수 설정
    # import os
    # os.environ["LANGFUSE_PUBLIC_KEY"] = LANGFUSE_DEFAULTS["public_key"]
    # os.environ["LANGFUSE_SECRET_KEY"] = LANGFUSE_DEFAULTS["secret_key"]
    # os.environ["LANGFUSE_HOST"] = LANGFUSE_DEFAULTS["host"]
    
    # 커스텀 콜백 핸들러 생성
    langfuse_handler = get_custom_langfuse_handler()

    load_dotenv() # OPENAI_API_KEY 
    
    state = {
        "query": "정확한 답을 알려줘서 고마워 ",
        "memory": [],
        "vectorstore": [],
        "file_search": [],
        "metadata": {},
        "model": "gpt-4.1-nano"
    }

    result = asyncio.run(graphastream(state, langfuse_handler))
    print(result)