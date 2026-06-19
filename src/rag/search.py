import os
import argparse

# Ensure we can import from src if running directly
import sys
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.append(project_root)

from src.rag.vectorstore import FaissVectorStore

def search_policy(query: str, top_k: int = 3, persist_dir: str = "db/vector_store"):
    """
    Loads the vector store and queries it for the given string.
    Returns a list of result dictionaries.
    """
    store = FaissVectorStore(persist_dir=persist_dir)
    try:
        store.load()
    except Exception as e:
        print(f"Error loading vector store: {e}")
        return []
        
    results = store.query(query, top_k=top_k)
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test RAG Search Pipeline")
    parser.add_argument("query", type=str, nargs="?", default="What is the policy for items marked as Non-Returnable?", help="Search query")
    parser.add_argument("--k", type=int, default=3, help="Number of results to return")
    args = parser.parse_args()
    
    print(f"\n--- Searching for: '{args.query}' ---\n")
    results = search_policy(args.query, top_k=args.k)
    
    if not results:
        print("No results found or index is empty.")
    else:
        for i, res in enumerate(results, 1):
            distance = res.get("distance", 0.0)
            meta = res.get("metadata", {})
            text = meta.get("text", "No text found in metadata.")
            source = meta.get("source", "Unknown Source")
            
            print(f"Result {i} (Distance: {distance:.4f}) | Source: {source}")
            print("-" * 50)
            print(text.strip())
            print("=" * 50 + "\n")
