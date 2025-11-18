"""
Тест Redis Queue Manager

Простой скрипт для проверки работы Redis Streams Queue
"""

import asyncio
from backend.queue.redis_queue_manager import RedisQueueManager, TaskPriority


async def test_handler(payload):
    """Тестовый обработчик задачи"""
    print(f"✅ Processing task: {payload}")
    await asyncio.sleep(2)  # Симуляция работы
    return {"status": "ok", "data": payload, "result": "success"}


async def main():
    """Основной тест"""
    print("🚀 Starting Redis Queue Manager Test")
    print("=" * 60)
    
    # 1. Создать manager
    qm = RedisQueueManager(
        redis_url="redis://localhost:6379/0",
        stream_name="test:tasks",
        consumer_group="test_workers"
    )
    
    try:
        # 2. Подключиться к Redis
        print("\n📡 Connecting to Redis...")
        await qm.connect()
        print("✅ Connected!")
        
        # 3. Регистрировать обработчик
        print("\n📝 Registering handler...")
        qm.register_handler("test", test_handler)
        
        # 4. Отправить тестовые задачи
        print("\n📤 Submitting test tasks...")
        task_ids = []
        for i in range(5):
            task_id = await qm.submit_task(
                task_type="test",
                payload={
                    "message": f"Test task #{i+1}",
                    "number": i+1
                },
                priority=TaskPriority.NORMAL.value
            )
            task_ids.append(task_id)
            print(f"   Task {i+1} submitted: {task_id[:16]}...")
        
        print(f"\n✅ Submitted {len(task_ids)} tasks")
        
        # 5. Запустить worker на 15 секунд
        print("\n🔄 Starting worker for 15 seconds...")
        print("   (Worker will process tasks in the background)")
        
        worker_task = asyncio.create_task(qm.start_worker())
        
        # Дать время на обработку
        await asyncio.sleep(15)
        
        # 6. Показать метрики
        print("\n📊 Metrics:")
        metrics = qm.get_metrics()
        for key, value in metrics.items():
            print(f"   {key}: {value}")
        
        # 7. Graceful shutdown
        print("\n🛑 Shutting down worker...")
        await qm.shutdown(timeout=10)
        
        print("\n✅ Test completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise
    finally:
        # Cleanup: удалить тестовый stream
        try:
            if qm._redis:
                await qm._redis.delete("test:tasks")
                await qm._redis.delete("test:tasks:dlq")
                print("\n🗑️  Cleaned up test streams")
        except:
            pass


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  Redis Queue Manager Test")
    print("="*60)
    print("\n⚠️  Make sure Redis is running on localhost:6379")
    print("   Start Redis: redis-server")
    print("   Or Docker: docker run -d -p 6379:6379 redis:latest\n")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
