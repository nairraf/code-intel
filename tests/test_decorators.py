import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from src.server import linker, parser
from src.knowledge_graph import KnowledgeGraph
from src.storage import VectorStore

knowledge_graph = KnowledgeGraph("tests/knowledge_graph_dummy.sqlite")
vector_store = VectorStore("memory://")

knowledge_graph._init_db()

async def run():
    # Parse chunks
    chunks = parser.parse_file('tests/dummy_api.py', project_root='/dummy_test_root')
    print("Parsed Chunks:")
    for c in chunks:
        print(f" - {c.symbol_name} uses: {[u.name for u in c.usages]}, decorators: {c.decorators}")
        
    # Upsert to DB
    dummy_vectors = [[0.0] * 768 for _ in chunks]
    vector_store.clear_project('/dummy_test_root')
    vector_store.upsert_chunks('/dummy_test_root', chunks, dummy_vectors)
    
    print("Direct VectorStore lookups:")
    print("verify_token:", vector_store.find_chunks_by_symbol('/dummy_test_root', 'verify_token'))
    print("Depends:", vector_store.find_chunks_by_symbol('/dummy_test_root', 'Depends'))

    # Link usages
    for chunk in chunks:
        linker.link_chunk_usages('/dummy_test_root', chunk)
        
    # Print edges
    print("\nKnowledge Graph Edges:")
    edges = knowledge_graph.get_edges()
    for e in edges:
        print(e)
        
if __name__ == '__main__':
    asyncio.run(run())
