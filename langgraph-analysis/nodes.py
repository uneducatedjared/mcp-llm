from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from prompts import *
from tools import *
from langgraph.types import Command
from langchain_deepseek import ChatDeepSeek
import os
from dotenv import load_dotenv
import json
import logging
from state import State
load_dotenv()

llm = ChatDeepSeek(
    model="deepseek-chat",
    temperature=0,
    max_retries=2,
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1" # DeepSeek API base URL
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
hander = logging.StreamHandler()
hander.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
hander.setFormatter(formatter)
logger.addHandler(hander)

def extract_json(text):
    if '```json' not in text:
        return text
    text = text.split('```json')[1].split('```')[0].strip()
    return text

def extract_answer(text):
    if '</think>' in text:
        answer = text.split("</think>")[-1]
        return answer.strip()
    
    return text

def create_planner_node(state: State):
    logger.info("***正在运行Create Planner node***")
    messages = [SystemMessage(content=PLAN_SYSTEM_PROMPT), HumanMessage(content=PLAN_CREATE_PROMPT.format(user_message = state['user_message']))]
    response = llm.invoke(messages)
    # response = response.model_dump_json(indent=4, exclude_none=True)
    # response = json.loads(response)
    print(response)
    plan = json.loads(extract_json(extract_answer(response.content))) # 更新plan 状态
    state['messages'] += [AIMessage(content=json.dumps(plan, ensure_ascii=False))]
    return Command(goto="execute_node", update={"plan": plan})

def update_planner_node(state: State):
    logger.info("***正在运行Update Planner node***")
    plan = state['plan']
    goal = plan['goal']
    state['messages'].extend([SystemMessage(content=PLAN_SYSTEM_PROMPT), HumanMessage(content=UPDATE_PLAN_PROMPT.format(plan = plan, goal=goal))])
    messages = state['messages']
    while True:
        try:
            response: AIMessage = llm.invoke(messages)
            response = response.model_dump_json(indent=4, exclude_none=True)
            response = json.loads(response)
            plan = json.loads(extract_json(extract_answer(response['content'])))
            state['messages']+=[AIMessage(content=json.dumps(plan, ensure_ascii=False))]
            return Command(goto="execute_node", update={"plan": plan})
        except Exception as e:
            messages += [HumanMessage(content=f"json格式错误:{e}")]

def execute_node(state: State):
    logger.info("***正在运行execute_node***")
  
    plan = state['plan']
    steps = plan['steps']
    current_step = None
    current_step_index = 0
    
    # 获取第一个未完成STEP
    for i, step in enumerate(steps):
        status = step['status']
        if status == 'pending':
            current_step = step
            current_step_index = i
            break
        
    logger.info(f"当前执行STEP:{current_step}")
    
    ## 此处只是简单跳转到report节点，实际应该根据当前STEP的描述进行判断，全部步骤都执行成功的情况
    if current_step is None or current_step_index == len(steps)-1:
        return Command(goto='report')
    
    messages_for_llm = state['observations'] + [
        SystemMessage(content=EXECUTE_SYSTEM_PROMPT),
        HumanMessage(content=EXECUTION_PROMPT.format(user_message=state['user_message'], step=current_step['description']))
    ]    
    tool_result = None
    last_tool_call_id = None # Keep track of the last tool_call_id

    while True:
        response:AIMessage = llm.bind_tools([create_file, str_replace, shell_exec]).invoke(messages_for_llm)
        print(type(response))
        print(type(response.tool_calls))
        messages_for_llm.append(response)
        tools = {"create_file": create_file, "str_replace": str_replace, "shell_exec": shell_exec}   
        # 标准化格式  
        if response.tool_calls:
            for tool_call in response.tool_calls:
                print(type(tool_call))
                print(tool_call)
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_call_id = tool_call["id"]
                logger.info(f"标准化格式调用 - tool_name:{tool_name}, tool_args:{tool_args}")
                tool_result = tools[tool_name].invoke(tool_args)
                logger.info(f"tool_name:{tool_name},tool_args:{tool_args}\ntool_result:{tool_result}")
                tool_message = ToolMessage(content=f"tool_name:{tool_name},tool_args:{tool_args}\ntool_result:{tool_result}", tool_call_id=tool_call_id)
                messages_for_llm.append(tool_message)
                last_tool_call_id = tool_call_id # Store the last tool_call_id
        else:    
            break
        
    logger.info(f"当前STEP执行总结:{extract_answer(response.content)}")
    
    state['messages'].append(AIMessage(content=extract_answer(response.content)))
    state['observations'] = messages_for_llm # Update observations with the full conversation for this step
    
    return Command(goto='update_planner', update={'plan': plan})