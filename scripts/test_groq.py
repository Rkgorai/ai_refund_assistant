import os
import sys
from dotenv import load_dotenv

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, ".env"))

from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

class TicketDecision(BaseModel):
    should_evaluate: bool = Field(description="True if the user has provided both the order ID and a clear reason for the return/issue.")
    order_id: str = Field(None, description="The numeric order ID the user wants to return.")
    issue_description: str = Field(None, description="The reason for the return or issue.")
    ai_response: str = Field(description="If should_evaluate is False, what should the AI say to the user to get the missing information? Keep it to 1 sentence.")

try:
    llm = ChatGroq(model=os.getenv("MODEL_NAME", "meta-llama/llama-4-scout-17b-16e-instruct"), temperature=0)
    structured_llm = llm.with_structured_output(TicketDecision)
    res = structured_llm.invoke("order id is 10109 and i dont like the color")
    print("Success:", res)
except Exception as e:
    import traceback
    traceback.print_exc()
