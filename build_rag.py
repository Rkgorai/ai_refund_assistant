import os
from src.rag.data_loader import load_all_documents
from src.rag.vectorstore import FaissVectorStore

def main():
    print("--- Building RAG Pipeline ---")
    
    # 1. Load documents
    docs = load_all_documents("policy_docs")
    
    if not docs:
        print("No documents found to index.")
        return
        
    # 2. Build and save vectorstore using the custom FaissVectorStore class
    store = FaissVectorStore(persist_dir="db/vector_store")
    store.build_from_documents(docs)

if __name__ == "__main__":
    # Ensure src is in python path if run from root
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    main()
