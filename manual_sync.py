import os
import asyncio
import mcp_cognee
from pathlib import Path

async def main():
    print("🚀 Starting manual sync for 'agentic_env'...")
    try:
        # Resolve path to ensure we are in the right spot
        project_path = str(Path("d:/Development/agentic_env").absolute())
        result = await mcp_cognee.sync_project_memory.fn(project_path)
        print(f"Result: {result}")
    except Exception as e:
        print(f"❌ Manual sync failed: {e}")

if __name__ == "__main__":
    if os.name == "nt":
        import os
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
