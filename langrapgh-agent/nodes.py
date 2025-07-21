from langchain_deepseek import ChatDeepSeek # Assuming this is available or you have it installed
import os
from dotenv import load_dotenv
import json
from langgraph.prebuilt import ToolNode
from state import AgentState
from tools import get_tools_async
import re
import asyncio
from langchain.schema import HumanMessage, SystemMessage

load_dotenv()

llm = ChatDeepSeek(
    model="deepseek-chat",
    temperature=0,
    max_retries=2,
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1" # DeepSeek API base URL
)

class CustomEncoder(json.JSONEncoder):
    def default(self, o):
        # 处理langchain消息对象
        if hasattr(o, "content"):
            return {"type": o.__class__.__name__, "content": o.content}
        return super().default(o)

'''
意图理解节点
1. 是根据型号查询数据库，返回对应的产品信息进行推荐，也可以提取多个产品型号进行对比
2. 是模糊查询用户给品类/应用场景 产品
'''
def intent_detection(state: AgentState) -> AgentState:
    """
    识别用户意图并返回相应的查询类型和参数
    
    Args:
        user_input (str): 用户输入的查询内容, 和用户的状态
    Returns:
        dict: 包含查询类型和参数的字典
    """
    user_input = state.get("user_input", "")
    # 定义提示词，引导LLM识别用户意图
    prompt = f"""
    请分析以下用户查询的意图，并以JSON格式返回结果：
    例如：
    1. mumble_search: 用户查询的内容涉及品类/应用场景，但没有具体的产品型号或参数。例如 “测试地暖的场景，应该选择哪些热成像仪。”
    2. detail_search: 用户查询的内容涉及具体的产品型号或参数。例如
    返回JSON的条件如下
    如果用户查询的内容涉及具体产品型号或者参数，返回"detail_search"类型，如果用户查询的没有涉及具体的产品型号或者参数，返回"mumble_search"类型,。
    如果是detail_search，从以下的产品线选择一个最相关的产品线填写到json中。
    如果是mumble_search，从以下的产品线选择两个最相关的产品线填写到json中。
    产品线包括：
    1. 电动气动工具
    2. 电子焊接工具
    3. 测试仪器
    4. 电源/负载
    5. 测试仪表
    6. 实验仪器
    7. 热成像仪
    8. 手动五金工具
    9. 辅料耗材
    10. 工业控制
    11. 工业物联网
    如果找不到相关的产品线，请在clarification_needed中返回True，并在clarification_question中询问用户。
    请确保 'product_lines' 字段总是包含一个列表，即使只有一个产品线。

    用户查询: "{user_input}"

    返回的JSON格式如下：
    {{
        "query_type": "detail_search | mumble_search",
        "query": "{user_input}",
        "product_lines": ["product_line1", "product_line2""]，
        "parameters": {{
            "models": ["model1", "model2"]  # 如果是detail_search，提取具体的产品型号，产品型号可选，可以为空列表
            "criteria": {{
                "parameter1": "value1",
                "parameter2": "value2" 
            }} # 如果是detail_search， 提取具体的产品参数，参数个数可选，可以为空对象
        }}
        "clarification_needed": false,  # 如果需要澄清问题，返回True
        "clarification_question": "小凡没有查询到相关问题的答案，请详细描述您的需求",  # 如果需要澄清问题，返回澄清问题
    }}
    """
    # 调用LLM获取意图分析结果
    try:

        response_content = llm.invoke(prompt).content
        # Assuming the LLM returns a JSON string that needs parsing
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_content)
        print(json_match.group(1))
        intent_data = json.loads(json_match.group(1))
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from LLM response: {response_content}")
        # Handle cases where LLM doesn't return valid JSON
        intent_data = {
            "query_type": None,
            "product_lines": [],
            "parameters": {"models": [], "criteria": {}},
            "clarification_needed": True,
            "clarification_question": "抱歉，我无法理解您的请求。请问您需要查询什么？"
        }
    except Exception as e:
        print(f"Error invoking LLM: {e}")
        # Handle other exceptions
        intent_data = {
            "query_type": None,
            "product_lines": [],
            "parameters": {"models": [], "criteria": {}},
            "clarification_needed": True,
            "clarification_question": "抱歉，我无法理解您的请求。请问您需要查询什么？"
        }
    new_state = state.copy()
    new_state["intent"] = intent_data.get("query_type")
    new_state["product_lines"] = intent_data.get("product_lines", [])
    new_state["product_params"] = intent_data.get("parameters", {"models": [], "criteria": {}})
    new_state["clarification_needed"] = intent_data.get("clarification_needed", False)
    new_state["clarification_question"] = intent_data.get("clarification_question", "")

    return new_state


# 场景匹配产品
from langchain.schema import HumanMessage, AIMessage

def mumble_search(state: AgentState) -> AgentState:
    tools = asyncio.run(get_tools_async())
    llm.bind_tools(tools)
    tool_node = ToolNode(tools)
    user_input = state.get("user_input", "")
    product_lines = state.get("product_lines", [])

    prompt = f"""
你现在是产品数据库检索助手。数据库表结构如下：
- id: int
- product_line: varchar(100)
- category: varchar(100)
- model: varchar(50)
- features: text
- application_scenarios: text
- parameters: json

请根据用户输入内容（user_input），在限定的产品线（product_lines）范围内，检索最相关的产品。
检索时优先考虑 application_scenarios、features、parameters 字段的匹配度，返回最符合用户需求的产品信息。

用户输入: {user_input}
限定产品线: {', '.join(product_lines)}

请以 JSON 格式返回产品列表，每个产品包含：model、features、application_scenarios、parameters 的核心信息。
"""

    try:
        # 添加系统提示或空的 AIMessage
        inputs_for_agent = {"messages": [
            SystemMessage(content="请根据用户需求返回产品信息。"),
            HumanMessage(content=prompt),
            AIMessage(content="")  # 补充一个空的AIMessage
            ]}

        result = tool_node.invoke(inputs_for_agent)
        print(result)
        formatted = json.dumps(result, ensure_ascii=False, indent=2, cls=CustomEncoder)
        print(formatted)
        state["product_info"] = result.get("products", [])

    except Exception as e:
        print(f"mumble_search error: {e}")
        state["product_info"] = []
    return state

# 参数匹配产品
def detail_search(state: AgentState) -> AgentState:
    pass

# 澄清问题节点+错误处理节点，处理intent问题和数据无法搜索到的问题
def clarification(state: AgentState) -> AgentState:
    """
    处理澄清请求，获取用户的澄清回答，并更新状态。
    """
    print(f"Entering clarification node. Question: {state.get('clarification_question')}")
    new_state = state.copy()
    # 如果澄清问题为空，给出默认问题
    if not new_state.get("clarification_question"):
        new_state["clarification_question"] = "请详细描述您的需求。"
    # 可以增加澄清次数计数，超过阈值直接结束
    new_state.setdefault("clarification_count", 0)
    new_state["clarification_count"] += 1
    if new_state["clarification_count"] > 3:
        new_state["response"] = "抱歉，无法理解您的需求，请联系人工客服。"
        new_state["intent"] = None
    return new_state

# 结果生成节点
def response_generation(state: AgentState):
    """根据状态中的产品信息和用户意图生成最终回答"""
    # 提取状态中的关键信息（避免冗余数据干扰）
    product_info = state.get("product_info", [])
    parameter_info = state.get("parameter_info", [])
    user_input = state.get("user_input", "")

    # 构建提示词（聚焦核心信息，明确生成规则）
    prompt = f"""
    请根据以下信息生成用户所需的推荐回答：
    1. 用户查询：{json.dumps(user_input, ensure_ascii=False)}
    2. 产品信息：{json.dumps(product_info, ensure_ascii=False)}
    3. 产品参数：{json.dumps(parameter_info, ensure_ascii=False)}

    生成要求：
    - 若没有相关产品信息，返回“抱歉，我没有找到相关产品。”
    - 若有产品信息，按以下逻辑生成：
      1. 先说明推荐结论
      2. 按产品相关性排序（优先展示更匹配用户查询的型号）
      3. 每个产品仅保留核心参数（重量、防护等级、关键优势）和特点，避免冗余
      4. 最后补充选择建议（如“轻量便携选XX，专业监测选XX”）
    - 语言简洁口语化，避免技术术语堆砌，总长度控制在300字内
    """

    # 调用LLM生成回答并更新状态
    try:
        response = llm.invoke(prompt).content
        state["response"] = response
    except Exception as e:
        print(f"生成回答时出错：{e}")
        state["response"] = "抱歉，暂时无法生成推荐结果，请稍后重试。"
    return state