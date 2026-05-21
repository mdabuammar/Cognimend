import asyncio
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
from core.openrouter_client import create_openrouter_client

# You must set OPENROUTER_API_KEY globally or let it be inherited from dotenv.

async def main():
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(__file__), 'backend', '.env'))
    except:
        pass

    client = create_openrouter_client('balanced')
    print('Testing Embedding...')
    try:
        emb = await client.get_embedding('test')
        print('Embedding len:', len(emb))
    except Exception as e:
        print('Embedding Error:', e)

    print('Testing Generation...')
    try:
        ans = await client.generate_answer('Hi', 'Ctx')
        print('Answer:', ans['model'])
    except Exception as e:
        print('Generation Error:', e)

asyncio.run(main())
