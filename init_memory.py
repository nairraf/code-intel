import asyncio
import cognee
import httpx
import os

async def check_ollama():
    """Verify Ollama is awake and the model is loaded."""
    print("📡 Checking Ollama connection...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:11434/api/tags", timeout=5.0)
            if response.status_code == 200:
                print("✅ Ollama is online.")
                return True
    except Exception:
        print("❌ ERROR: Ollama is not running on localhost:11434")
        return False

async def main():
    # 1. Ensure Ollama is ready before we even touch Cognee
    if not await check_ollama():
        return

    print("🧹 Cleaning system for a fresh start...")
    try:
        await cognee.prune.prune_system(metadata=True)
        await cognee.prune.prune_data()
    except Exception as e:
        print(f"⚠️ Prune warning (safe to ignore): {e}")

    print("🧠 Adding project context...")
    # Add data in a single batch
    await cognee.add([
        "Flutter app with a Python middle-layer API.",
        "Agentic development environment using local memory."
    ])
    
    print("⚙️ Cognifying (Building Graph & Vectors)...")
    print("⏳ This step can take 1-2 minutes on the first run. Please wait...")
    
    # We use a try-except here because Cognify is the most intensive part
    try:
        await cognee.cognify()
        print("✅ Cognify complete!")
    except Exception as e:
        print(f"❌ Cognify failed: {e}")
        return

    print("🔍 Testing Search...")
    from cognee import SearchType
    results = await cognee.search(query_text="tech stack", query_type=SearchType.CHUNKS)
    
    if results:
        print(f"🎉 SUCCESS! Found memory: {results[0]}")
    else:
        print("❓ No search results found.")

if __name__ == "__main__":
    # Windows-specific fix for the "Proactor" event loop
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())