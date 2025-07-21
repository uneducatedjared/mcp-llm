import os
import json
import sys
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client  # Import sse_client
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from dotenv import load_dotenv
from langchain.schema import HumanMessage
from langchain_deepseek import ChatDeepSeek # Assuming this is available or you have it installed

load_dotenv()

# Custom JSON encoder to handle Langchain message content
class CustomEncoder(json.JSONEncoder):
    def default(self, o):
        # 处理langchain消息对象
        if hasattr(o, "content"):
            return {"type": o.__class__.__name__, "content": o.content}
        return super().default(o)

# Initialize the DeepSeek LLM
llm = ChatDeepSeek(
    model="deepseek-chat",
    temperature=0,
    max_retries=2,
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1" # DeepSeek API base URL
)

# Check for command-line arguments
if len(sys.argv) < 2:
    print("Usage: python client_langchain_deepseek_chat_bind_tools_sse.py <server_url>")
    print("Example: python client_langchain_deepseek_chat_bind_tools_sse.py http://localhost:3000/sse")
    sys.exit(1)

server_url = sys.argv[1] # MCP SSE server URL

# Global holder for the active mcp session (used to tool adapter)
mcp_client = None

# Client startup and agent execution
async def run_agent():
    global mcp_client
    print(f"Attempting to connect to MCP SSE server at: {server_url}")
    try:
        # Use sse_client to establish the connection
        async with sse_client(server_url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                mcp_client = type("MCPClientHolder", (), {"session": session})() # Store the session
                print("MCP client initialized.")
                
                # Load available tools from the MCP server
                tools = await load_mcp_tools(session)
                print("Agent created with tools:", [tool.name for tool in tools])
                
                # Create the LangGraph agent
                agent = create_react_agent(llm, tools, prompt="你是一家工业品公司的推荐助手，帮助用户找到合适的产品。请根据用户的查询提供相关产品信息。")
                
                print("MCP Client Started! Type 'quit' to exit.")
                while True:
                    query = input("\nQuery: ").strip()
                    if query.lower() == "quit":
                        break
                    if not query:
                        print("Query cannot be empty. Please enter something.")
                        continue

                    # Send user query to agent and print formatted response
                    inputs_for_agent = {"messages": [HumanMessage(content=query)]}
                    response = await agent.ainvoke(inputs_for_agent)
                    try:
                        formatted = json.dumps(response, ensure_ascii=False, indent=2, cls=CustomEncoder)
                    except Exception as e:
                        formatted = str(response)
                        print(f"Warning: Could not format response as JSON: {e}")
                    print("\nResponse:")
                    print(formatted)
    except Exception as e:
        print(f"An error occurred during MCP connection or agent execution: {e}")
        print("Please ensure the MCP SSE server is running and accessible at the provided URL.")


if __name__ == "__main__":
    asyncio.run(run_agent())