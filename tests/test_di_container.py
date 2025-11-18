"""
Tests for Dependency Injection Container (Phase 2)
Service lifecycle and dependency management
"""

import pytest
import asyncio
from di_container import DIContainer, ServiceLifecycle, reset_container


class TestDIContainer:
    """Test dependency injection container"""
    
    def test_container_creation(self):
        """Test DI container can be created"""
        container = DIContainer()
        assert container is not None
        assert container.is_initialized() is False
        assert len(container.list_services()) == 0
    
    def test_register_service(self):
        """Test registering a service"""
        container = DIContainer()
        
        def create_service():
            return {"value": 42}
        
        container.register("test_service", create_service, singleton=True)
        
        services = container.list_services()
        assert "test_service" in services
        assert len(services) == 1
    
    @pytest.mark.asyncio
    async def test_get_service(self):
        """Test getting a service instance"""
        container = DIContainer()
        
        def create_service():
            return {"value": 42}
        
        container.register("test_service", create_service, singleton=True)
        
        service = await container.get("test_service")
        
        assert service is not None
        assert service["value"] == 42
    
    @pytest.mark.asyncio
    async def test_singleton_service(self):
        """Test singleton services return same instance"""
        container = DIContainer()
        
        call_count = []
        
        def create_service():
            call_count.append(1)
            return {"value": len(call_count)}
        
        container.register("singleton", create_service, singleton=True)
        
        # Get service twice
        service1 = await container.get("singleton")
        service2 = await container.get("singleton")
        
        # Should be same instance
        assert service1 is service2
        assert service1["value"] == 1  # Factory called only once
        assert len(call_count) == 1
    
    @pytest.mark.asyncio
    async def test_non_singleton_service(self):
        """Test non-singleton services return new instances"""
        container = DIContainer()
        
        call_count = []
        
        def create_service():
            call_count.append(1)
            return {"value": len(call_count)}
        
        container.register("factory", create_service, singleton=False)
        
        # Get service twice
        service1 = await container.get("factory")
        service2 = await container.get("factory")
        
        # Should be different instances
        assert service1 is not service2
        assert service1["value"] == 1
        assert service2["value"] == 2
        assert len(call_count) == 2
    
    @pytest.mark.asyncio
    async def test_async_service_factory(self):
        """Test async service factories"""
        container = DIContainer()
        
        async def create_service():
            await asyncio.sleep(0.01)
            return {"async": True}
        
        container.register("async_service", create_service, singleton=True)
        
        service = await container.get("async_service")
        
        assert service["async"] is True
    
    @pytest.mark.asyncio
    async def test_initialize_all_services(self):
        """Test initializing all services in order"""
        container = DIContainer()
        
        init_order = []
        
        def create_service_a():
            init_order.append("A")
            return "A"
        
        def create_service_b():
            init_order.append("B")
            return "B"
        
        def create_service_c():
            init_order.append("C")
            return "C"
        
        container.register("service_a", create_service_a)
        container.register("service_b", create_service_b)
        container.register("service_c", create_service_c)
        
        await container.initialize_all()
        
        assert container.is_initialized() is True
        assert init_order == ["A", "B", "C"]
    
    @pytest.mark.asyncio
    async def test_service_not_found(self):
        """Test error when getting non-existent service"""
        container = DIContainer()
        
        with pytest.raises(KeyError) as exc_info:
            await container.get("nonexistent")
        
        assert "not registered" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_shutdown_all_services(self):
        """Test shutting down all services"""
        container = DIContainer()
        
        shutdown_called = []
        
        class ServiceWithShutdown:
            async def shutdown(self):
                shutdown_called.append(True)
        
        async def create_service():
            return ServiceWithShutdown()
        
        container.register("service", create_service, singleton=True)
        await container.initialize_all()
        
        await container.shutdown_all()
        
        assert len(shutdown_called) == 1
        assert container.is_initialized() is False
    
    @pytest.mark.asyncio
    async def test_service_status(self):
        """Test getting service status"""
        container = DIContainer()
        
        def create_service():
            return {"test": True}
        
        # Before registration
        status_before = container.get_service_status("test_service")
        assert status_before["exists"] is False
        
        # After registration
        container.register("test_service", create_service, singleton=True)
        status_after = container.get_service_status("test_service")
        
        assert status_after["exists"] is True
        assert status_after["initialized"] is False
        assert status_after["singleton"] is True
        
        # After initialization
        await container.get("test_service")
        status_initialized = container.get_service_status("test_service")
        
        assert status_initialized["initialized"] is True
        assert status_initialized["has_instance"] is True
    
    @pytest.mark.asyncio
    async def test_reset_container(self):
        """Test resetting global container"""
        from di_container import get_container, reset_container
        
        # Get container and register service
        container1 = get_container()
        container1.register("test", lambda: "test1")
        
        # Reset
        reset_container()
        
        # Get new container
        container2 = get_container()
        
        # Should be fresh container
        assert len(container2.list_services()) == 0


class TestServiceLifecycle:
    """Test service lifecycle management"""
    
    @pytest.mark.asyncio
    async def test_sync_factory(self):
        """Test synchronous factory function"""
        def factory():
            return "test_value"
        
        lifecycle = ServiceLifecycle(factory, singleton=True)
        
        instance = await lifecycle.get_instance()
        
        assert instance == "test_value"
        assert lifecycle.initialized is True
    
    @pytest.mark.asyncio
    async def test_async_factory(self):
        """Test asynchronous factory function"""
        async def factory():
            await asyncio.sleep(0.01)
            return "async_value"
        
        lifecycle = ServiceLifecycle(factory, singleton=True)
        
        assert lifecycle.is_async is True
        
        instance = await lifecycle.get_instance()
        
        assert instance == "async_value"
        assert lifecycle.initialized is True
    
    @pytest.mark.asyncio
    async def test_singleton_lifecycle(self):
        """Test singleton lifecycle returns same instance"""
        call_count = []
        
        def factory():
            call_count.append(1)
            return len(call_count)
        
        lifecycle = ServiceLifecycle(factory, singleton=True)
        
        instance1 = await lifecycle.get_instance()
        instance2 = await lifecycle.get_instance()
        
        assert instance1 == instance2
        assert instance1 == 1
        assert len(call_count) == 1
    
    @pytest.mark.asyncio
    async def test_non_singleton_lifecycle(self):
        """Test non-singleton lifecycle creates new instances"""
        call_count = []
        
        def factory():
            call_count.append(1)
            return len(call_count)
        
        lifecycle = ServiceLifecycle(factory, singleton=False)
        
        instance1 = await lifecycle.get_instance()
        instance2 = await lifecycle.get_instance()
        
        assert instance1 != instance2
        assert instance1 == 1
        assert instance2 == 2
        assert len(call_count) == 2
    
    @pytest.mark.asyncio
    async def test_shutdown_with_method(self):
        """Test shutdown calls service shutdown method"""
        shutdown_called = []
        
        class ServiceWithShutdown:
            async def shutdown(self):
                shutdown_called.append(True)
        
        async def factory():
            return ServiceWithShutdown()
        
        lifecycle = ServiceLifecycle(factory, singleton=True)
        
        # Get instance
        await lifecycle.get_instance()
        
        # Shutdown
        await lifecycle.shutdown()
        
        assert len(shutdown_called) == 1
        assert lifecycle.instance is None
        assert lifecycle.initialized is False
