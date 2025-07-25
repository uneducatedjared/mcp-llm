from typing import Literal, List
from pydantic import BaseModel
from langgraph.graph import MessagesState

class Step(BaseModel):
    title: str =""
    description: str=""
    status: Literal["pending", "completed"]


class Plan(BaseModel):
    goal: str=""
    thought: str=""
    steps: List[Step] = []

class State(MessagesState):
    user_message: str =""
    plan: Plan
    observations: List=[]
    final_report: str=""