from typing import TypedDict, Dict, Any, List
from langgraph import add_message
from langgraph.graph import StateGraph, START, END
from typing import Annotated

# 现有结构是追加的消息列表
def State(TypedDict):
    user_input: str # 用户输入的查询
    intent: str # 用户意图，由意图识别节点提取
    product_params: Dict[str, Any] # 产品参数，意图识别参数提取
    scenario: str # 场景描述，由意图识别参数提取
    product_info: List[Dict[str, Any]] # 产品信息列表，由产品查询节点填充
    clarification_needed: bool # 是否需要澄清问题
    clarification_question: str # 澄清问题，由澄清节点生成
    clarification_answer: str # 用户对澄清问题的回答
    response: str # 最终响应，由响应生成节点填充




# 初始化数据
graph_builder = StateGraph(State)