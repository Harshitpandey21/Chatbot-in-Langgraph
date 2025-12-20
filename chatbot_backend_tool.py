from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import tool
from langgraph.graph.message import add_messages
import sqlite3
import requests
import yfinance as yf
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

llm = ChatOpenAI()

search_tool= DuckDuckGoSearchRun(region= "us-en")

@tool
def calculator(first_num:float, second_num:float, operation:str)->dict:
    """
    Perform a basic arithmetic operations on the provided input
    supported operations are: add,sub,mul,div.
    """
    try:  
      if operation =="add":
        result = first_num+second_num
      elif operation == "sub":
        result = first_num-second_num
      elif operation == "mul":
        result = first_num*second_num
      elif operation == "div":
        if second_num == 0:
            return {"error": "Division by zero is not allowed"}
        result = first_num/second_num
      else:
        return {"error": "Invalid operation"}

      return {"result": result}
    except Exception as e:
        return {"error": str(e)}
    
@tool
def stock_price(symbol: str) -> dict:
   """
   Give the latest stock price for the given symbol(eg. 'TSLA')
   using Alpha Vantage with API key in the url.
   """
   url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey= MK5DKEJTIEFO3G1L"
   r = requests.get(url)
   return r.json()

@tool 
def date_time()->str:
   """Provide current date and time."""
   return datetime.now().strftime("%d-%m-%Y %H:%M:%S")

@tool
def list_chat_threads() -> list:
    """List all available chat thread IDs."""
    return retrieve_all_threads()

tools = [search_tool, calculator, stock_price, date_time,list_chat_threads]
llm_with_tools = llm.bind_tools(tools)


class ChatState(TypedDict):
    messages : Annotated[list[BaseMessage], add_messages]

def chat_node(state: ChatState):
    messages = state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}
tool_node = ToolNode(tools)

conn = sqlite3.connect(database = "chatbot.db", check_same_thread = False)
checkpointer = SqliteSaver(conn = conn)

graph = StateGraph(ChatState)
graph.add_node("chat_node", chat_node)
graph.add_node("tools", tool_node)

graph.add_edge(START, "chat_node")

graph.add_conditional_edges("chat_node",tools_condition)
graph.add_edge('tools', 'chat_node')

chatbot = graph.compile(checkpointer=checkpointer)
def retrieve_all_threads():
    all_threads = set()
    for checkpoint in checkpointer.list(None):
        all_threads.add(checkpoint.config['configurable']['thread_id'])

    return list(all_threads)