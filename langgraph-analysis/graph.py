from nodes import (
    create_planner_node,
    update_planner_node,
    execute_node
)
from langgraph.graph import StateGraph, START, END
from state import State

def build_graph():
    builder = StateGraph(State)
    builder.add_edge(START, "create_planner")
    builder.add_node("create_planner", create_planner_node)
    builder.add_node("update_planner", update_planner_node)
    builder.add_node("execute_node", execute_node)
    # builder.add_node("report", report_node)
    # builder.add_edge("report", END)
    return builder.compile()


graph = build_graph()

inputs = {"user_message": "对所给文档进行分析，生成分析报告，文档路径为student_habits_performance.csv", 
          "plan": None,
          "observations": [], 
          "final_report": ""}

graph.invoke(inputs, {"recursion_limit":100})