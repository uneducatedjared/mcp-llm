from langchain_deepseek import ChatDeepSeek # Assuming this is available or you have it installed
import os
from graph_state import State
from dotenv import load_dotenv
import json

load_dotenv()

llm = ChatDeepSeek(
    model="deepseek-chat",
    temperature=0,
    max_retries=2,
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1" # DeepSeek API base URL
)

'''
意图理解节点
1. 是根据型号查询数据库，返回对应的产品信息进行推荐，也可以提取多个产品型号进行对比
2. 是模糊查询用户给品类/应用场景 产品
'''
def intent_detection(user_input):
    """
    识别用户意图并返回相应的查询类型和参数
    
    Args:
        user_input (str): 用户输入的查询内容
    
    Returns:
        dict: 包含查询类型和参数的字典
    """
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
    如果找不到相关的产品线，请返回其他
    {{
        "query_type": "detail_search | mumble_search",
        "query": "{user_input}",
        "product_lines": ["product_line1", "product_line2""]，
        "parameters": {{
            "models": ["model1", "model2"]  # 如果是detail_search，提取具体的产品型号，产品型号可选
            "criteria": {{
                "parameter1": "value1",
                "parameter2": "value2" 
            }} # 如果是detail_search， 提取具体的产品参数，参数个数可选
        }}
    }}


    """
    
    # 调用LLM获取意图分析结果
    response = llm.invoke(prompt)
    return response

# 参数匹配产品
def mumble_search(prompt):
    pass

# 场景匹配场景
def detail_search(prompt):
    pass

def process_user_query(user_input):
    """处理用户查询并返回结果"""
    intent = intent_detection(user_input)
    intent = json.loads(intent)  # 假设返回的是JSON字符串
    product_lines = intent["product_lines"]
    if intent["product_lines"] == "其他":
        return "抱歉，您提到的产品线不在我们的支持范围内。请尝试其他查询。"
    
    elif intent["query_type"] == "detail_search":
        # parameters = intent["parameters"]
        # models = parameters["models"]
        # criteria = parameters["criteria"]
        intent = json.dumps(intent, ensure_ascii=False)
        detail_search(intent)

       
    elif intent["query_type"] == "mumble_search":
        product_lines = intent["product_lines"].get("pro", "")
        try:
            # product_line1 = product_lines[0]
            # product_line2 = product_lines[1]
            intent = json.dumps(intent, ensure_ascii=False)
            mumble_search(intent)

        except IndexError:
            return "无法识别您的查询类型，请尝试重新描述您的问题。"
    else:
        return "无法识别您的查询类型，请尝试重新描述您的问题。"