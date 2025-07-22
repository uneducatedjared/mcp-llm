from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from state import AgentState
from nodes import (
    intent_detection,
    mumble_search,
    detail_search,
    clarification,
    response_generation
)

def xiaofanAgent():
    graph = StateGraph(AgentState)
    graph.add_edge(START, "intent_detection")

    graph.add_node("intent_detection", intent_detection)
    graph.add_node("detail_search", detail_search)
    graph.add_node("mumble_search", mumble_search)
    graph.add_node("clarification", clarification)
    graph.add_node("response_generation", response_generation)

    graph.set_entry_point("intent_detection")

    # intent_detection分支
    graph.add_conditional_edges(
        "intent_detection",
        lambda state: (
            "clarification" if state.get("clarification_needed", False)
            else state.get("intent")
        )
    )

    # detail_search分支
    graph.add_conditional_edges(
        "detail_search",
        lambda state: (
            "clarification" if not state.get("product_info")
            else "response_generation"
        )
    )

    # mumble_search分支
    graph.add_conditional_edges(
        "mumble_search",
        lambda state: (
            "clarification" if not state.get("product_info")
            else "response_generation"
        )
    )

    # clarification分支
    graph.add_conditional_edges(
        "clarification",
        lambda state: (
            state.get("intent") if state.get("clarification_answer") else "clarification"
        )
    )

    graph.add_edge("response_generation", END)

    return graph

def build_graph():
    memory = MemorySaver()
    builder = xiaofanAgent()
    # return builder.compile(checkpointer=memory)
    return builder.compile()

graph = build_graph()

# 入口参数要和AgentState字段一致
inputs = {
    "user_input": "推荐适合户外场景的热成像仪"
}

graph.invoke(inputs)