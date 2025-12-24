from fastapi import FastAPI, WebSocket
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import uvicorn
import uuid
import json
import time

from ccc_chatbot_custom import graph

# -----------------------------
# App
# -----------------------------
app = FastAPI(
    title="CCC-ChatBot-Server",
    version="1.0.0",
    description="Fast API-style server for CCC chatbot",
)

# -----------------------------
# Schemas
# -----------------------------
class QueryRequest(BaseModel):
    query: str = Field(..., description="Query to run")
    thread_id: str | None = Field(default=None, description="Thread ID of user")


class QueryResponse(BaseModel):
    answer: str
    steps: list[str]
    thread_id: str


# -----------------------------
# Core Graph Runner (NON-STREAM)
# -----------------------------
def run_graph(query: str, thread_id: str) -> tuple[str, list[str]]:
    config = {"configurable": {"thread_id": thread_id}}

    final_answer = ""
    steps_log: list[str] = []

    for step, chunk in enumerate(
        graph.stream(
            {"messages": [{"role": "user", "content": query}]},
            config=config,
        ),
        start=1,
    ):
        for node, update in chunk.items():
            msg = update["messages"][-1]
            content = msg.content if hasattr(msg, "content") else str(msg)

            steps_log.append(
                f"Step {step} | Node: {node}\nResponse: {content}"
            )
            final_answer = content

    return final_answer, steps_log


# -----------------------------
# SSE STREAMING
# -----------------------------
def sse_graph_stream(query: str, thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}

    # Send thread id first
    yield f"data: {json.dumps({'event': 'init', 'thread_id': thread_id})}\n\n"

    try:
        for step, chunk in enumerate(
            graph.stream(
                {"messages": [{"role": "user", "content": query}]},
                config=config,
            ),
            start=1,
        ):
            for node, update in chunk.items():
                msg = update["messages"][-1]
                content = msg.content if hasattr(msg, "content") else str(msg)

                yield f"data: {json.dumps({
                    'event': 'step',
                    'step': step,
                    'node': node,
                    'content': content
                })}\n\n"

                time.sleep(0.03)

        yield f"data: {json.dumps({'event': 'done'})}\n\n"

    except GeneratorExit:
        return


# -----------------------------
# Endpoints
# -----------------------------
@app.get("/")
def root():
    return {"message": "Welcome to the CCC Chatbot Server"}

@app.get("/health")
def health():
    return {"status": "healthy", "code": 200}

# -------- JSON (final answer + steps)
@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    thread_id = req.thread_id or str(uuid.uuid4())
    answer, steps = run_graph(req.query, thread_id)

    return {
        "answer": answer,
        "steps": steps,
        "thread_id": thread_id,
    }

# -------- SSE STREAM
@app.post("/query/stream")
def query_stream(req: QueryRequest):
    thread_id = req.thread_id or str(uuid.uuid4())

    return StreamingResponse(
        sse_graph_stream(req.query, thread_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )

# -------- WEBSOCKET STREAM
@app.websocket("/query/ws")
async def query_ws(websocket: WebSocket):
    await websocket.accept()

    try:
        data = await websocket.receive_json()
        query = data["query"]
        thread_id = data.get("thread_id") or str(uuid.uuid4())

        await websocket.send_json({
            "event": "init",
            "thread_id": thread_id,
        })

        config = {"configurable": {"thread_id": thread_id}}

        for step, chunk in enumerate(
            graph.stream(
                {"messages": [{"role": "user", "content": query}]},
                config=config,
            ),
            start=1,
        ):
            for node, update in chunk.items():
                msg = update["messages"][-1]
                content = msg.content if hasattr(msg, "content") else str(msg)

                await websocket.send_json({
                    "event": "step",
                    "step": step,
                    "node": node,
                    "content": content,
                })

        await websocket.send_json({"event": "done"})

    except Exception:
        pass
    finally:
        await websocket.close()

# uvicorn try:app --reload


# @app.post("/suggestions", response_model=SuggestionResponse)
# def get_suggestions(req: QueryRequest):
#     thread_id = req.thread_id or str(uuid.uuid4())

#     messages = run_graph(req.query, thread_id)

#     suggestions = []

#     for msg in messages:
#         if isinstance(msg, AIMessage) and msg.content.startswith("Suggested follow-up"):
#             suggestions = [
#                 line.replace("- ", "").strip()
#                 for line in msg.content.split("\n")
#                 if line.startswith("- ")
#             ]

#     return {
#         "suggestions": suggestions,
#         "thread_id": thread_id,
#     }



SUGGESTION_PROMPT = """
You are an assistant that generates follow-up query suggestions.

Rules:
- Use the provided final answer.
- If the final answer contains a question, generate possible answers to that question.
- If the final answer is neutral, suggest queries related to Cloud Computing Cell (CCC) and Related to neutral answer.
- Generate between 2 and 3 suggestions.
- Each suggestion must contain 3 to 6 words.

Final Answer:
{final_answer}
"""


def next_suggestions(state):
    last_message = state["messages"][-1]

    if not isinstance(last_message, AIMessage):
        raise ValueError("Expected last message to be AIMessage")

    final_answer = last_message.content
    prompt = SUGGESTION_PROMPT.format(final_answer=final_answer)

    response = grader_model.with_structured_output(
        SuggestPrompt
    ).invoke(prompt)

    # ✅ Convert structured output → text
    suggestions_text = "\n".join(
        f"- {s}" for s in response.suggestion_list
    )

    return {
        "messages": [
            AIMessage(
                content=f"Suggested follow-up questions:\n{suggestions_text}"
            )
        ]
    }
