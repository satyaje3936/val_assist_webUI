import streamlit as st
import logging
import streamlit as st
import numpy as np
import math
import random
import connectors.openai_connector as Openai
import json
import os
from openai import AzureOpenAI
import httpx

# Initialize logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
API_VERSION = "2024-12-01-preview"
BASE_URL = "https://laasapim01.laas.icloud.intel.com/azopenai"
DEFAULT_DEPLOYMENT = "gpt-4o"

class AzureOpenAIChat:
    def __init__(self):
        self.client = create_azure_client()
        self.conversation_history = [
            {"role": "system", "content": "You are a helpful assistant specializing in software development and validation."}
        ]
    
    def chat(self, user_message, max_tokens=1000, temperature=0.7):
        """Send a message and get response while maintaining conversation history"""
        try:
            # Add user message to history
            self.conversation_history.append({"role": "user", "content": user_message})
            
            response = self.client.chat.completions.create(
                model=DEFAULT_DEPLOYMENT,
                messages=self.conversation_history,
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            assistant_message = response.choices[0].message.content
            
            # Add assistant response to history
            self.conversation_history.append({"role": "assistant", "content": assistant_message})
            
            return assistant_message
        except Exception as e:
            logger.error(f"Error in chat: {e}")
            return f"Error: {str(e)}"
    
    def clear_history(self):
        """Clear conversation history except system message"""
        self.conversation_history = [self.conversation_history[0]]
    
    def get_token_count(self):
        """Estimate token count of current conversation"""
        try:
            import tiktoken
            encoding = tiktoken.get_encoding("cl100k_base")
            total_tokens = 0
            for message in self.conversation_history:
                total_tokens += len(encoding.encode(message["content"]))
            return total_tokens
        except:
            # Fallback estimation
            total_chars = sum(len(msg["content"]) for msg in self.conversation_history)
            return total_chars // 4

# Initialize Azure OpenAI client
def create_azure_client():
    api_key = os.environ.get("OPENAI_KEY")
    if not api_key:
        raise ValueError("OPENAI_KEY environment variable not set")
    
    client = AzureOpenAI(
        api_version=API_VERSION,
        api_key=api_key,
        base_url=BASE_URL,
        default_headers={"Ocp-Apim-Subscription-Key": api_key},
        http_client=httpx.Client(verify=False)
    )
    return client

# Simple chat completion
def simple_chat(user_message):
    try:
        client = create_azure_client()
        
        response = client.chat.completions.create(
            model=DEFAULT_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_message}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error in chat completion: {e}")
        return f"Error: {str(e)}"

def streamlit_chat_app():
    st.title('Chat with Azure OpenAI')
    
    # Initialize chat bot in session state
    if 'chat_bot' not in st.session_state:
        try:
            st.session_state.chat_bot = AzureOpenAIChat()
            st.session_state.messages = []
        except Exception as e:
            st.error(f"Failed to initialize chat: {e}")
            return
    
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("What would you like to know?"):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get AI response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = st.session_state.chat_bot.chat(prompt)
                st.markdown(response)
        
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})
    
    # Sidebar controls
    with st.sidebar:
        st.subheader("Chat Controls")
        
        if st.button("Clear Conversation"):
            st.session_state.chat_bot.clear_history()
            st.session_state.messages = []
            st.rerun()
        
        # Show token count
        if hasattr(st.session_state, 'chat_bot'):
            token_count = st.session_state.chat_bot.get_token_count()
            st.metric("Estimated Tokens", token_count)
        
        # Temperature control
        temperature = st.slider("Response Creativity", 0.0, 1.0, 0.7, 0.1)
        st.session_state.temperature = temperature

def app():
    logger.info("chat with AI app is started")
    st.title('Chat with AI')
    st.write("This is the Chat with AI page.")
    # User input for chat
    # user_input = st.text_input("You:", "")
    # if st.button("Send"):
    #     if user_input:
    #         # Call OpenAI API to get response
    #         #response = simple_chat(user_input)
    #         response = streamlit_chat_app(user_input)
    #         st.write("AI:", response)
    #     else:
    #         st.warning("Please enter a message.")
    streamlit_chat_app()
