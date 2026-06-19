import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from src.rag.vectorstore import FaissVectorStore

def main():
    load_dotenv()

    model_name = "llama-3.1-8b-instant"
    
    if not os.environ.get("GROQ_API_KEY"):
        print("Error: GROQ_API_KEY not found in environment variables.")
        return

    print("Initializing Groq LLM...")
    llm = ChatGroq(model=model_name, temperature=0)

    print("Loading RAG Vector Store...")
    try:
        store = FaissVectorStore(persist_dir="db/vector_store")
        store.load()
    except Exception as e:
        print(f"Failed to load Vector Store: {e}")
        return

    system_prompt = """You are an AI assistant helping users understand a company's return policy.
Answer the user's question ONLY using the provided Context from the official policy documents.
If the answer is not in the Context, say "I don't know based on the provided policy."

Context:
{context}"""

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{question}")
    ])

    print("\n" + "="*50)
    print("📘 RAG Verification Chatbot (With Memory)")
    print("Type 'exit' or 'quit' to stop.")
    print("="*50 + "\n")

    chat_history = []

    while True:
        try:
            user_input = input("You: ")
            if user_input.lower() in ['exit', 'quit']:
                break
            if not user_input.strip():
                continue
            
            # 1. Retrieve context from RAG
            results = store.query(user_input, top_k=3)
            context_texts = []
            for r in results:
                if "metadata" in r and "text" in r["metadata"]:
                    context_texts.append(r["metadata"]["text"])
            
            context_string = "\n\n---\n\n".join(context_texts)
            
            # 2. Pass context, history, and question to LLM
            messages = prompt_template.invoke({
                "context": context_string,
                "chat_history": chat_history,
                "question": user_input
            })
            
            response = llm.invoke(messages)
            print(f"\nAssistant: {response.content}\n")
            
            # 3. Save to memory for the next turn
            chat_history.append(HumanMessage(content=user_input))
            chat_history.append(AIMessage(content=response.content))
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nError: {e}\n")

if __name__ == "__main__":
    main()
