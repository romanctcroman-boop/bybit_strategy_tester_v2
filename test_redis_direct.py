"""
Тестовый скрипт - проверка Redis напрямую
"""
import asyncio
import redis.asyncio as redis

async def test_redis():
    print("🔌 Connecting to Redis...")
    client = await redis.from_url("redis://localhost:6379", decode_responses=True)
    
    print("✍️  Writing test data...")
    result = await client.zadd("test:metrics", {"value1": 1.0, "value2": 2.0})
    print(f"✅ ZADD result: {result}")
    
    print("📖 Reading data immediately...")
    data = await client.zrange("test:metrics", 0, -1, withscores=True)
    print(f"📊 Data: {data}")
    
    print("🔑 Listing all keys...")
    keys = await client.keys("*")
    print(f"📋 Keys: {keys}")
    
    await client.close()
    print("✅ Done")

if __name__ == "__main__":
    asyncio.run(test_redis())
