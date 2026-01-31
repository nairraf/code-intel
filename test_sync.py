import asyncio
import os
import sys
from mcp_cognee import sync_project_memory, check_ollama

async def main():
    print("Testing sync_project_memory...")
    if not await check_ollama():
        print("Ollama is not running!")
        return
    
    # We call the tool function directly
    # Note: This will use the same environment setup as the real MCP server
    result = await sync_project_memory()
    print(f"RESULT: {result}")

if __name__ == "__main__":
    asyncio.run(main())
