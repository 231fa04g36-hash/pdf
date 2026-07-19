import os
import sys
import shutil

# Add parent directory of scripts/ (which is backend/) to python path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings

def reset_dev_vectorstore() -> None:
    print("Resetting local developer vector store...")
    chroma_dir = os.path.abspath(settings.CHROMA_PERSIST_DIR)
    
    if os.path.exists(chroma_dir):
        try:
            shutil.rmtree(chroma_dir)
            print(f"Successfully deleted ChromaDB directory at: {chroma_dir}")
        except Exception as e:
            print(f"Error deleting ChromaDB directory at '{chroma_dir}': {e}")
    else:
        print(f"ChromaDB directory '{chroma_dir}' does not exist, nothing to delete.")
        
    print("Vector store reset complete. (Broom)")

if __name__ == "__main__":
    reset_dev_vectorstore()
