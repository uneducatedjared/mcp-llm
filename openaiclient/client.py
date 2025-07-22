import asyncio
import json
import os
import sys
from typing import List
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.sse import sse_client
from openai import AsyncOpenAI


class MCPClient:
    def __init__(self, model_name: str, base_url: str, api_key: str, server_urls: List[str]):
        """
        初始化 MCP 客户端，对接 OpenAI 接口。
        :param model_name: 使用的模型名称，例如 "deepseek-chat"。
        :param base_url: OpenAI 接口的基础地址，例如 "https://api.deepseek.com/v1"。
        :param api_key: OpenAI API 密钥，用于身份验证。
        :param server_urls: SSE 服务地址列表，用于连接后端服务。
        """
        self.model_name = model_name
        self.server_urls = server_urls
        self.sessions = {}  # 存储每个服务的会话信息，格式：server_id -> (session, session_context, streams_context)
        self.tool_mapping = {}  # 工具映射：prefixed_name -> (session, original_tool_name)

        # 初始化 OpenAI 异步客户端
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    async def initialize_sessions(self):
        """
        初始化所有 SSE 服务连接，并获取工具列表。
        """
        for i, server_url in enumerate(self.server_urls):
            server_id = f"server{i}"  # 为每个服务生成唯一标识
            # 创建 SSE 客户端连接上下文
            streams_context = sse_client(url=server_url)
            streams = await streams_context.__aenter__()
            session_context = ClientSession(*streams)
            session = await session_context.__aenter__()
            await session.initialize()

            # 存储会话相关信息
            self.sessions[server_id] = (session, session_context, streams_context)

            # 获取工具列表并建立映射
            response = await session.list_tools()
            for tool in response.tools:
                prefixed_name = f"{server_id}_{tool.name}"  # 为工具名添加服务前缀（避免重名）
                self.tool_mapping[prefixed_name] = (session, tool.name)
            print(f"已连接 {server_url}，工具列表：{[tool.name for tool in response.tools]}")

    async def cleanup(self):
        """
        清理所有会话及资源，确保资源正确释放。
        """
        for server_id, (session, session_context, streams_context) in self.sessions.items():
            await session_context.__aexit__(None, None, None)  # 退出会话上下文
            await streams_context.__aexit__(None, None, None)  # 退出 SSE 连接上下文
        print("所有会话已清理完毕")

    async def process_query(self, query: str) -> str:
        """
        处理用户查询，通过模型判断是否调用工具，并返回最终结果。

        :param query: 用户输入的查询字符串
        :return: 整理后的回答文本
        """
        messages = [{"role": "user", "content": query}]  # 初始化消息列表

        # 收集可用工具
        available_tools = []
        for server_id, (session, _, _) in self.sessions.items():
            response = await session.list_tools()
            for tool in response.tools:
                prefixed_name = f"{server_id}_{tool.name}"
                available_tools.append({
                    "type": "function",
                    "function": {
                        "name": prefixed_name,
                        "description": tool.description,
                        "parameters": tool.inputSchema,
                    },
                })

        # 向模型发送初始请求
        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            tools=available_tools,
        )

        final_text = []  # 存储最终回答内容
        message = response.choices[0].message
        final_text.append(message.content or "")  # 添加模型的初始回答

        # 处理工具调用
        while message.tool_calls:
            for tool_call in message.tool_calls:
                prefixed_name = tool_call.function.name
                if prefixed_name in self.tool_mapping:
                    session, original_tool_name = self.tool_mapping[prefixed_name]
                    tool_args = json.loads(tool_call.function.arguments)
                    try:
                        result = await session.call_tool(original_tool_name, tool_args)
                    except Exception as e:
                        result = {"content": f"调用工具 {original_tool_name} 失败：{str(e)}"}
                        print(result["content"])
                    final_text.append(f"[调用工具 {prefixed_name} 参数：{tool_args}]")
                    final_text.append(f"工具返回：{result.content}")
                    messages.extend([
                        {
                            "role": "assistant",
                            "tool_calls": [{
                                "id": tool_call.id,
                                "type": "function",
                                "function": {"name": prefixed_name, "arguments": json.dumps(tool_args)},
                            }],
                        },
                        {"role": "tool", "tool_call_id": tool_call.id, "content": str(result.content)},
                    ])
                else:
                    print(f"工具 {prefixed_name} 未找到")
                    final_text.append(f"工具 {prefixed_name} 未找到")

            # 获取工具调用后的模型回答
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=available_tools,
            )
            message = response.choices[0].message
            if message.content:
                final_text.append(message.content)

        return "\n".join(final_text)

    async def chat_loop(self):
        """
        启动交互式聊天循环，接收用户输入并显示回答。
        """
        print("\nMCP 客户端已启动，可输入问题，输入 'quit' 退出")
        while True:
            try:
                query = input("\n提问：").strip()
                if query.lower() == "quit":
                    break
                response = await self.process_query(query)
                print("\n" + response)
            except Exception as e:
                print(f"\n处理错误：{str(e)}")


async def main():
    load_dotenv()  # 加载环境变量
    """
    主函数：初始化并运行 MCP 客户端。
    """
    # 从环境变量获取配置
    model_name = "deepseek-chat"
    base_url = "https://api.deepseek.com/v1"
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("未配置 API_KEY，请检查环境变量")
        sys.exit(1)

    # SSE 服务地址列表
    server_urls = ["http://localhost:3000/sse"]

    # 初始化客户端
    client = MCPClient(model_name=model_name, base_url=base_url, api_key=api_key, server_urls=server_urls)
    try:
        await client.initialize_sessions()
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())