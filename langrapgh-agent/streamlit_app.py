import streamlit as st
from graph import graph


def xiaofan_fullstack():
    st.title("智能客服助手")

    # 初始化 agent
    if "agent" not in st.session_state:
        st.session_state.ag
    # 初始化会话状态
    if "messages" not in st.session_state:
        st.session_state.messages = []
        st.session_state.context = {}  # 用于存储对话上下文
    
    # 显示历史消息
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # 处理用户输入
    if user_input := st.chat_input("请输入您的问题..."):
        # 添加用户消息到会话状态
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # 准备输入参数
        inputs = {
            "user_input": user_input,
            **st.session_state.context  # 包含之前的对话上下文
        }
        
        # 调用智能体
        with st.spinner("思考中..."):
            try:
                result = graph.invoke(inputs)
                # 更新对话上下文
                st.session_state.context = result.get("context", {})
                # 获取回复内容
                response = result.get("response", "抱歉，我无法回答这个问题。")
                
                # 添加助手消息到会话状态
                st.session_state.messages.append({"role": "assistant", "content": response})
                with st.chat_message("assistant"):
                    st.markdown(response)
            except Exception as e:
                error_msg = f"处理过程中发生错误: {str(e)}"
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                with st.chat_message("assistant"):
                    st.error(error_msg)
if __name__ == "__main__":
    xiaofan_fullstack()