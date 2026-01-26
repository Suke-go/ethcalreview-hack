import asyncio
import sys
sys.path.insert(0, '.')

from app.services.llm_client import create_llm_client

async def test():
    print("Creating client...")
    try:
        c = create_llm_client('openai', 'test-key')
        print(f"Client created: {type(c)}")
        print(f"Has sync client: {hasattr(c, '_sync_client') and c._sync_client is not None}")
        print(f"Has async client: {c.client is not None}")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test())
