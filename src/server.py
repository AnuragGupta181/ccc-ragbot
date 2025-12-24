# uvicorn src.server:app --host 0.0.0.0 --port 8000 --reload

import uuid
from typing import Optional, Generator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.graph import MessagesState


# 🔹 IMPORT YOUR GRAPH
from src.app import graph   # <-- adjust import if needed


# =========================
# FastAPI App
# =========================
app = FastAPI(
    title="CCC Chatbot API",
    version="1.0.0",
    description="LangGraph-powered chatbot with memory, RAG, and streaming"
)

# =========================
# CORS (React support)
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # change to frontend domain in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# Request / Response Models
# =========================
class ChatRequest(BaseModel):
    query: str
    thread_id: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    thread_id: str
    tool_type: str | None = None
    tool_name: str | None = None

class SuggestRequest(BaseModel):
    final_answer: str | None = None
    thread_id: str | None = None


class SuggestResponse(BaseModel):
    suggestions: list[str]
    thread_id: str | None = None


# =========================
# Helpers
# =========================
def extract_final_answer(messages):
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            return msg
    return None


def extract_tool_metadata(messages):
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            return {
                "tool_name": msg.name,
                "tool_type": "rag" if "retrieve" in msg.name.lower() else "custom"
            }
    return {"tool_name": None, "tool_type": "none"}


# =========================
# REST Endpoint
# =========================
@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):

    # 🔹 Thread handling
    thread_id = request.thread_id or str(uuid.uuid4())

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    # 🔹 Run graph (invoke mode)
    result = graph.invoke(
        {
            "messages": [
                HumanMessage(content=request.query)
            ]
        },
        config=config
    )

    messages = result["messages"]

    # 🔹 Extract final answer
    final_msg = extract_final_answer(messages)
    tool_meta = extract_tool_metadata(messages)

    return ChatResponse(
        answer=final_msg.content if final_msg else "I don't know.",
        thread_id=thread_id,
        tool_type=tool_meta["tool_type"],
        tool_name=tool_meta["tool_name"]
    )


# =========================
# Streaming Endpoint (SSE)
# =========================
@app.post("/chat/stream")
def chat_stream(request: ChatRequest):

    thread_id = request.thread_id or str(uuid.uuid4())

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    def event_stream() -> Generator[str, None, None]:
        yield f"event: thread\n"
        yield f"data: {thread_id}\n\n"

        for chunk in graph.stream(
            {
                "messages": [
                    HumanMessage(content=request.query)
                ]
            },
            config=config
        ):
            for node, update in chunk.items():

                # 🔹 Node-level logs (CLI-style)
                yield f"event: node\n"
                yield f"data: 🔹 Node: {node}\n\n"

                for msg in update["messages"]:
                    if isinstance(msg, AIMessage):
                        yield f"event: message\n"
                        yield f"data: {msg.content}\n\n"

                    elif isinstance(msg, ToolMessage):
                        yield f"event: tool\n"
                        yield f"data: Tool={msg.name}\n\n"

        yield "event: done\n"
        yield "data: end\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream"
    )

SUGGESTION_PROMPT = """
You are an assistant that generates follow-up query suggestions.

Rules:
- Use the provided final answer.
- If the final answer contains a question, generate possible answers to that question.
- If the final answer is neutral, suggest queries related to Cloud Computing Cell (CCC) and related to the neutral answer.
- Generate between 2 and 3 suggestions.
- Each suggestion must contain 3 to 6 words.
- Do NOT number the suggestions.
- Do NOT use bullets.

Final Answer:
{final_answer}
"""

from langchain_core.messages import AIMessage

def get_last_ai_answer(messages):
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            return msg.content
    return None

from langchain_deepseek import ChatDeepSeek
import os
response_model = ChatDeepSeek(
    model="google/gemini-2.5-flash-lite-preview-09-2025",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    api_base="https://openrouter.ai/api/v1",
    extra_body={"reasoning": {"enabled": True}},
)


@app.post("/suggest", response_model=SuggestResponse)
def suggest(request: SuggestRequest):

    # 🔹 Decide source of final answer
    final_answer = request.final_answer

    if not final_answer:
        if not request.thread_id:
            return SuggestResponse(
                suggestions=[],
                thread_id=None
            )

        config = {
            "configurable": {
                "thread_id": request.thread_id
            }
        }

        # Load memory from graph
        state = graph.get_state(config)
        final_answer = get_last_ai_answer(state["messages"])

        if not final_answer:
            return SuggestResponse(
                suggestions=[],
                thread_id=request.thread_id
            )

    # 🔹 Generate suggestions
    prompt = SUGGESTION_PROMPT.format(final_answer=final_answer)

    response = response_model.invoke(
        [{"role": "user", "content": prompt}]
    )

    # 🔹 Parse suggestions (one per line)
    suggestions = [
        line.strip("-• ").strip()
        for line in response.content.split("\n")
        if line.strip()
    ]

    return SuggestResponse(
        suggestions=suggestions,
        thread_id=request.thread_id
    )


# =========================
# Health Check
# =========================
@app.get("/health")
def health():
    return {"status": "ok", "code": 200, "message": "CCC Chatbot API is healthy."}
@app.get("/")
def root():
    return {
        "welcome": "Welcome to the CCC Chatbot API",
        "description": (
            "This API powers the CCC Intelligent Chatbot built using LangGraph, "
            "memory (checkpointer), RAG, web search, and custom tools. "
            "It supports multi-turn conversations, query rewriting, tool routing, "
            "context grading, and real-time streaming."
        ),

        "available_endpoints": {
            "/docs": {
                "method": "GET",
                "purpose": "Interactive API documentation (Swagger UI)"
            },
            "/chat": {
                "method": "POST",
                "type": "REST",
                "purpose": "Standard chatbot interaction (recommended for frontend)",
                "body": {
                    "query": "string (required)",
                    "thread_id": "string (optional, used for memory)"
                }
            },
            "/chat/stream": {
                "method": "POST",
                "type": "SSE (Streaming)",
                "purpose": "Streams node-by-node execution and responses (debug/developer mode)"
            },
            "/health": {
                "method": "GET",
                "purpose": "Health check for monitoring and deployment"
            }
        },

        "chatbot_capabilities": [
            "Multi-turn conversational memory",
            "Automatic question rewriting for unclear queries",
            "Context relevance grading before answering",
            "Tool-aware reasoning (RAG, web, code, custom tools)",
            "Fallback handling when information is unavailable",
            "Streaming and non-streaming responses"
        ],

        "available_tools": {
            "get_weather": "Fetches real-time weather information for a city",
            "web_search": "Performs general web search for up-to-date information",
            "tavily_search": "High-quality AI-optimized web search",
            "code_executor": "Safely executes code snippets and returns output",
            "retrieve_info_tool": "Retrieves general CCC society information",
            "retrieve_domains_tool": "Fetches CCC technical domains and details",
            "retrieve_events_tool": "Retrieves past and upcoming CCC events",
            "retrieve_faqs_tool": "Answers frequently asked CCC-related questions",
            "retrieve_members_tool": "Fetches CCC members and alumni information",
            "retrieve_faculty_tool": "Retrieves faculty coordinators and mentors"
        },
    }
