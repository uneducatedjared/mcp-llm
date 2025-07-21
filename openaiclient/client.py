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
        ��ʼ�� MCP �ͻ��ˣ����� OpenAI �ӿڡ�
        :param model_name: ʹ�õ�ģ�����ƣ����� "deepseek-chat"��
        :param base_url: OpenAI �ӿڵĻ�����ַ������ "https://api.deepseek.com/v1"��
        :param api_key: OpenAI API ��Կ�����������֤��
        :param server_urls: SSE �����ַ�б��������Ӷ����������
        """
        self.model_name = model_name
        self.server_urls = server_urls
        self.sessions = {}  # �洢ÿ���������ĻỰ���������ģ�server_id -> (session, session_context, streams_context)
        self.tool_mapping = {}  # ����ӳ�䣺prefixed_name -> (session, original_tool_name)

        # ��ʼ�� OpenAI �첽�ͻ���
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    async def initialize_sessions(self):
        """
        ��ʼ�������� SSE �����������ӣ�����ȡ���ù����б�
        """
        for i, server_url in enumerate(self.server_urls):
            server_id = f"server{i}"  # Ϊÿ������������Ψһ��ʶ��
            # ���� SSE �ͻ��˲�����������
            streams_context = sse_client(url=server_url)
            streams = await streams_context.__aenter__()
            session_context = ClientSession(*streams)
            session = await session_context.__aenter__()
            await session.initialize()

            # �洢�Ự����������
            self.sessions[server_id] = (session, session_context, streams_context)

            # ��ȡ�����б�����ӳ��
            response = await session.list_tools()
            for tool in response.tools:
                prefixed_name = f"{server_id}_{tool.name}"  # Ϊ��������ӷ�����ǰ׺
                self.tool_mapping[prefixed_name] = (session, tool.name)
            print(f"�����ӵ� {server_url}�������б�{[tool.name for tool in response.tools]}")

    async def cleanup(self):
        """
        �������лỰ��������Դ��ȷ������Դй©��
        """
        for server_id, (session, session_context, streams_context) in self.sessions.items():
            await session_context.__aexit__(None, None, None)  # �˳��Ự������
            await streams_context.__aexit__(None, None, None)  # �˳� SSE ��������
        print("���лỰ������")

    async def process_query(self, query: str) -> str:
        """
        �����û�����Ȼ���Բ�ѯ��ͨ�����ߵ���������񲢷��ؽ����

        :param query: �û�����Ĳ�ѯ�ַ�����
        :return: �����Ļظ��ı���
        """
        messages = [{"role": "user", "content": query}]  # ��ʼ����Ϣ�б�

        # �ռ����п��ù���
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

        # ��ģ�ͷ��ͳ�ʼ����
        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            tools=available_tools,
        )

        final_text = []  # �洢���ջظ�����
        message = response.choices[0].message
        final_text.append(message.content or "")  # ���ģ�͵ĳ�ʼ�ظ�

        # �����ߵ���
        while message.tool_calls:
            for tool_call in message.tool_calls:
                prefixed_name = tool_call.function.name
                if prefixed_name in self.tool_mapping:
                    session, original_tool_name = self.tool_mapping[prefixed_name]
                    tool_args = json.loads(tool_call.function.arguments)
                    try:
                        result = await session.call_tool(original_tool_name, tool_args)
                    except Exception as e:
                        result = {"content": f"���ù��� {original_tool_name} ����{str(e)}"}
                        print(result["content"])
                    final_text.append(f"[���ù��� {prefixed_name} ����: {tool_args}]")
                    final_text.append(f"���߽��: {result.content}")
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
                    print(f"���� {prefixed_name} δ�ҵ�")
                    final_text.append(f"���� {prefixed_name} δ�ҵ�")

            # ��ȡ���ߵ��ú�ĺ����ظ�
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
        ���������н���ʽ�Ի�ѭ���������û����벢��ʾ�ظ���
        """
        print("\nMCP �ͻ���������������������⣬���� 'quit' �˳���")
        while True:
            try:
                query = input("\n����: ").strip()
                if query.lower() == "quit":
                    break
                response = await self.process_query(query)
                print("\n" + response)
            except Exception as e:
                print(f"\n��������: {str(e)}")


async def main():
    load_dotenv()  # ���ػ�������
    """
    ������ڣ��������ò����� MCP �ͻ��ˡ�
    """
    # �ӻ���������ȡ����
    model_name = "deepseek-chat"
    base_url = "https://api.deepseek.com/v1"
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("δ���� API_KEY ����������")
        sys.exit(1)

    # ���� SSE ��������ַ�б�
    server_urls = ["http://localhost:3000/sse"]

    # ���������пͻ���
    client = MCPClient(model_name=model_name, base_url=base_url, api_key=api_key, server_urls=server_urls)
    try:
        await client.initialize_sessions()
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
