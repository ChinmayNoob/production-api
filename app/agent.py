from typing import Optional
from typing_extensions import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langsmith import traceable

from app.config import get_settings


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    error: Optional[str]
    retry_count: int
    model_used: Optional[str]


class ProductionAgent:
    def __init__(self):
        s = get_settings()
        self.primary_llm = ChatOpenAI(model=s.primary_model, temperature=0, timeout=30, max_retries=0)
        self.fallback_llm = ChatOpenAI(model=s.fallback_model, temperature=0, timeout=30, max_retries=0)
        self.max_retries = s.max_retries
        self.graph = self._build_graph()

    def _build_graph(self):
        agent = self

        def call_primary(state: AgentState) -> dict:
            try:
                response = agent.primary_llm.invoke(state["messages"])
                s = get_settings()
                return {
                    "messages": [AIMessage(content=response.content)],
                    "model_used": s.primary_model,
                    "error": None,
                }
            except Exception as e:
                return {"error": str(e)}

        def call_fallback(state: AgentState) -> dict:
            try:
                response = agent.fallback_llm.invoke(state["messages"])
                s = get_settings()
                return {
                    "messages": [AIMessage(content=response.content)],
                    "model_used": s.fallback_model,
                    "error": None,
                    "retry_count": state["retry_count"] + 1,
                }
            except Exception as e:
                return {
                    "error": f"{state.get('error', '')} | Fallback error: {e}",
                    "retry_count": state["retry_count"] + 1,
                }

        def route_after_primary(state: AgentState) -> str:
            if state.get("error") is None:
                return "done"
            if state["retry_count"] < agent.max_retries:
                return "fallback"
            return "error_out"

        def route_after_fallback(state: AgentState) -> str:
            if state.get("error") is None:
                return "done"
            if state["retry_count"] < agent.max_retries:
                return "fallback"
            return "error_out"

        graph = StateGraph(AgentState)
        graph.add_node("call_primary", call_primary)
        graph.add_node("call_fallback", call_fallback)

        graph.add_edge(START, "call_primary")

        graph.add_conditional_edges("call_primary", route_after_primary, {
            "done": END,
            "fallback": "call_fallback",
            "error_out": END,
        })
        graph.add_conditional_edges("call_fallback", route_after_fallback, {
            "done": END,
            "fallback": "call_fallback",
            "error_out": END,
        })

        return graph.compile()

    @traceable(name="production_agent_invoke")
    def invoke(self, message: str) -> dict:
        result = self.graph.invoke({
            "messages": [HumanMessage(content=message)],
            "error": None,
            "retry_count": 0,
            "model_used": None,
        })

        return {
            "response": result["messages"][-1].content,
            "model_used": result["model_used"],
            "error": result["error"],
            "retry_count": result["retry_count"],
        }