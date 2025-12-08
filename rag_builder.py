# rag_builder.py - Standalone utility to build and save the RAG vector index

import os
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import Chroma

# --- Configuration (Must match your main JARVIS script) ---
KB_PATH = "D:/Jarvis/kb" 
OLLAMA_EMBEDDING_MODEL = "nomic-embed-text:latest" 
OLLAMA_API_URL = "http://localhost:11434/api/generate"
RAG_COLLECTION_NAME = "jarvis_kb_collection"
RAG_PERSIST_DIR = "./chroma_db"

def build_rag_index():
    print("=" * 50)
    print(" RAG Knowledge Base Builder")
    print("=" * 50)
    
    # Check if the KB path exists
    if not os.path.isdir(KB_PATH):
        print(f"❌ ERROR: Knowledge Base directory not found: {KB_PATH}")
        print("Please create the folder and add .txt files.")
        return

    # 1. Load documents
    print(f"Loading documents from {KB_PATH}...")
    try:
        # Load all .txt files in the directory
        loader = DirectoryLoader(KB_PATH, glob="**/*.txt", loader_cls=TextLoader, silent_errors=True)
        documents = loader.load()
    except Exception as e:
        print(f"❌ ERROR: Could not load documents: {e}")
        return

    if not documents:
        print("✅ No documents found. Index will not be created.")
        return

    # 2. Split documents into small chunks
    print(f"Found {len(documents)} documents. Splitting into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    texts = text_splitter.split_documents(documents)
    print(f"Total {len(texts)} chunks created for embedding.")

    # 3. Define the Ollama Embedding Model
    embeddings = OllamaEmbeddings(model=OLLAMA_EMBEDDING_MODEL, base_url=OLLAMA_API_URL)

    # 4. Create new Vector Store (THIS IS THE RESOURCE-INTENSIVE STEP)
    print("🧠 Starting embedding calculation (This may take several minutes)...")
    if os.path.isdir(RAG_PERSIST_DIR):
        import shutil
        print(f"⚠️ Deleting existing directory: {RAG_PERSIST_DIR}")
        shutil.rmtree(RAG_PERSIST_DIR)

    db = Chroma.from_documents(
        texts, 
        embeddings, 
        collection_name=RAG_COLLECTION_NAME, 
        persist_directory=RAG_PERSIST_DIR
    )
    
    print("✨ Indexing complete.")
    print(f"Vectors saved to disk at {RAG_PERSIST_DIR}")
    print("You can now run your main JARVIS script, and it will load this index instantly.")

if __name__ == "__main__":
    build_rag_index()