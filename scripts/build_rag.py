import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

from src.rag.data_loader import load_all_documents
from src.rag.vectorstore import FaissVectorStore

def main():
    print("--- Building RAG Pipeline ---")
    
    # 1. Load documents
    docs = load_all_documents(os.path.join(project_root, "policy_docs"))
    
    if not docs:
        print("No documents found to index.")
        return
        
    # 2. Build and save vectorstore using the custom FaissVectorStore class
    store = FaissVectorStore(persist_dir=os.path.join(project_root, "db", "vector_store"))
    store.build_from_documents(docs)

if __name__ == "__main__":
    main()
