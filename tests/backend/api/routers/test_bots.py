"""
Comprehensive test suite for backend/api/routers/bots.py

Target: 100% coverage (90.70% → 100%)
Missing lines to cover: 93, 107, 118, 128

Test Structure:
- TestListBots: GET / endpoint (pagination, validation)
- TestGetBot: GET /{bot_id} endpoint (success, 404)
- TestStartBot: POST /{bot_id}/start endpoint
- TestStopBot: POST /{bot_id}/stop endpoint
- TestDeleteBot: POST /{bot_id}/delete endpoint
- TestBotEdgeCases: Edge cases, special characters
- TestBotIntegration: Full lifecycle scenarios
- TestResponseFormats: Response consistency
- TestMockDataSeeding: Seeding behavior
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def reset_bots():
    """Reset bots state between tests"""
    from backend.api.routers import bots
    
    bots._BOTS.clear()
    yield
    bots._BOTS.clear()


class TestListBots:
    """Test GET /api/v1/bots endpoint - list all bots with pagination"""

    def test_list_bots_default_params(self, client: TestClient):
        """List bots with default pagination (limit=50, offset=0)"""
        response = client.get("/api/v1/bots/")
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
        assert len(data["items"]) <= 50  # Default limit

    def test_list_bots_with_limit(self, client: TestClient):
        """Test pagination with custom limit"""
        response = client.get("/api/v1/bots/", params={"limit": 2})
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["items"]) <= 2
        assert data["total"] >= len(data["items"])

    def test_list_bots_with_offset(self, client: TestClient):
        """Test pagination with offset"""
        # Get first page
        response1 = client.get("/api/v1/bots/", params={"limit": 1, "offset": 0})
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Get second page
        response2 = client.get("/api/v1/bots/", params={"limit": 1, "offset": 1})
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Total should be same
        assert data1["total"] == data2["total"]
        
        # Items should be different (if total > 1)
        if data1["total"] > 1:
            assert data1["items"][0]["id"] != data2["items"][0]["id"]

    def test_list_bots_both_params(self, client: TestClient):
        """Test pagination with both limit and offset"""
        response = client.get("/api/v1/bots/", params={"limit": 1, "offset": 1})
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["items"]) <= 1

    def test_list_bots_min_limit(self, client: TestClient):
        """Test minimum valid limit (1)"""
        response = client.get("/api/v1/bots/", params={"limit": 1})
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["items"]) <= 1

    def test_list_bots_max_limit(self, client: TestClient):
        """Test maximum valid limit (500)"""
        response = client.get("/api/v1/bots/", params={"limit": 500})
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["items"]) <= 500

    def test_list_bots_validation_limit_too_small(self, client: TestClient):
        """Test validation: limit < 1 should fail"""
        response = client.get("/api/v1/bots/", params={"limit": 0})
        assert response.status_code == 422  # Validation error

    def test_list_bots_validation_limit_too_large(self, client: TestClient):
        """Test validation: limit > 500 should fail"""
        response = client.get("/api/v1/bots/", params={"limit": 501})
        assert response.status_code == 422  # Validation error

    def test_list_bots_validation_negative_offset(self, client: TestClient):
        """Test validation: offset < 0 should fail"""
        response = client.get("/api/v1/bots/", params={"offset": -1})
        assert response.status_code == 422  # Validation error

    def test_list_bots_response_structure(self, client: TestClient):
        """Verify response structure and bot fields"""
        response = client.get("/api/v1/bots/")
        assert response.status_code == 200
        
        data = response.json()
        if len(data["items"]) > 0:
            bot = data["items"][0]
            assert "id" in bot
            assert "name" in bot
            assert "strategy" in bot
            assert "symbols" in bot
            assert "capital_allocated" in bot
            assert "status" in bot
            assert "created_at" in bot
            assert isinstance(bot["symbols"], list)
            assert isinstance(bot["capital_allocated"], (int, float))

    def test_list_bots_empty_offset(self, client: TestClient, reset_bots):
        """Test list with offset beyond total items"""
        response = client.get("/api/v1/bots/", params={"offset": 1000})
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["items"]) == 0  # No items at this offset
        assert data["total"] >= 0

    def test_list_bots_pagination_consistency(self, client: TestClient):
        """Verify total count is consistent across pages"""
        response1 = client.get("/api/v1/bots/", params={"limit": 1, "offset": 0})
        response2 = client.get("/api/v1/bots/", params={"limit": 2, "offset": 0})
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Total should be same regardless of pagination params
        assert response1.json()["total"] == response2.json()["total"]


class TestGetBot:
    """Test GET /api/v1/bots/{bot_id} endpoint - get single bot"""

    def test_get_bot_success(self, client: TestClient):
        """Get bot by valid ID"""
        # First, list bots to get a valid ID
        list_response = client.get("/api/v1/bots/")
        assert list_response.status_code == 200
        
        bots = list_response.json()["items"]
        if len(bots) > 0:
            bot_id = bots[0]["id"]
            
            # Get specific bot
            response = client.get(f"/api/v1/bots/{bot_id}")
            assert response.status_code == 200
            
            bot = response.json()
            assert bot["id"] == bot_id
            assert "name" in bot
            assert "strategy" in bot

    def test_get_bot_not_found(self, client: TestClient):
        """Get bot with non-existent ID should return 404"""
        response = client.get("/api/v1/bots/nonexistent_bot_id_12345")
        assert response.status_code == 404
        
        error = response.json()
        assert "detail" in error
        assert "not found" in error["detail"].lower()

    def test_get_bot_response_format(self, client: TestClient):
        """Verify get_bot response matches Bot model"""
        list_response = client.get("/api/v1/bots/")
        bots = list_response.json()["items"]
        
        if len(bots) > 0:
            bot_id = bots[0]["id"]
            response = client.get(f"/api/v1/bots/{bot_id}")
            assert response.status_code == 200
            
            bot = response.json()
            # Verify all required fields
            assert isinstance(bot["id"], str)
            assert isinstance(bot["name"], str)
            assert isinstance(bot["strategy"], str)
            assert isinstance(bot["symbols"], list)
            assert isinstance(bot["capital_allocated"], (int, float))
            assert isinstance(bot["status"], str)
            assert isinstance(bot["created_at"], str)

    def test_get_bot_empty_id(self, client: TestClient):
        """Get bot with empty ID"""
        response = client.get("/api/v1/bots/")
        # Empty ID maps to list endpoint, not an error
        assert response.status_code == 200

    def test_get_bot_special_characters(self, client: TestClient):
        """Get bot with special characters in ID"""
        response = client.get("/api/v1/bots/bot@#$%")
        assert response.status_code == 404  # Won't exist


class TestStartBot:
    """Test POST /api/v1/bots/{bot_id}/start endpoint"""

    def test_start_bot_success(self, client: TestClient):
        """Start bot successfully"""
        # Get a valid bot ID
        list_response = client.get("/api/v1/bots/")
        bots = list_response.json()["items"]
        assert len(bots) > 0
        
        bot_id = bots[0]["id"]
        
        # Start the bot
        response = client.post(f"/api/v1/bots/{bot_id}/start")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert data["status"] == "awaiting_start"
        assert "message" in data
        assert "start" in data["message"].lower()

    def test_start_bot_not_found(self, client: TestClient):
        """Start non-existent bot should return 404"""
        response = client.post("/api/v1/bots/nonexistent_bot/start")
        assert response.status_code == 404
        
        error = response.json()
        assert "detail" in error
        assert "not found" in error["detail"].lower()

    def test_start_bot_status_change(self, client: TestClient, reset_bots):
        """Verify bot status changes to awaiting_start"""
        # Get bot
        list_response = client.get("/api/v1/bots/")
        bots = list_response.json()["items"]
        assert len(bots) > 0
        
        bot_id = bots[0]["id"]
        
        # Start bot
        start_response = client.post(f"/api/v1/bots/{bot_id}/start")
        assert start_response.status_code == 200
        
        # Verify status changed
        get_response = client.get(f"/api/v1/bots/{bot_id}")
        bot = get_response.json()
        assert bot["status"] == "awaiting_start"

    def test_start_bot_response_format(self, client: TestClient):
        """Verify start_bot response format"""
        list_response = client.get("/api/v1/bots/")
        bots = list_response.json()["items"]
        assert len(bots) > 0
        
        bot_id = bots[0]["id"]
        response = client.post(f"/api/v1/bots/{bot_id}/start")
        assert response.status_code == 200
        
        data = response.json()
        assert "ok" in data
        assert "status" in data
        assert "message" in data
        assert isinstance(data["ok"], bool)

    def test_start_bot_idempotency(self, client: TestClient, reset_bots):
        """Starting already-started bot should succeed"""
        list_response = client.get("/api/v1/bots/")
        bots = list_response.json()["items"]
        assert len(bots) > 0
        
        bot_id = bots[0]["id"]
        
        # Start twice
        response1 = client.post(f"/api/v1/bots/{bot_id}/start")
        response2 = client.post(f"/api/v1/bots/{bot_id}/start")
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json()["ok"] is True
        assert response2.json()["ok"] is True


class TestStopBot:
    """Test POST /api/v1/bots/{bot_id}/stop endpoint"""

    def test_stop_bot_success(self, client: TestClient):
        """Stop bot successfully"""
        list_response = client.get("/api/v1/bots/")
        bots = list_response.json()["items"]
        assert len(bots) > 0
        
        bot_id = bots[0]["id"]
        
        # Stop the bot
        response = client.post(f"/api/v1/bots/{bot_id}/stop")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert data["status"] == "awaiting_stop"
        assert "message" in data
        assert "stop" in data["message"].lower()

    def test_stop_bot_not_found(self, client: TestClient):
        """Stop non-existent bot should return 404"""
        response = client.post("/api/v1/bots/nonexistent_bot/stop")
        assert response.status_code == 404
        
        error = response.json()
        assert "detail" in error
        assert "not found" in error["detail"].lower()

    def test_stop_bot_status_change(self, client: TestClient, reset_bots):
        """Verify bot status changes to awaiting_stop"""
        list_response = client.get("/api/v1/bots/")
        bots = list_response.json()["items"]
        assert len(bots) > 0
        
        bot_id = bots[0]["id"]
        
        # Stop bot
        stop_response = client.post(f"/api/v1/bots/{bot_id}/stop")
        assert stop_response.status_code == 200
        
        # Verify status changed
        get_response = client.get(f"/api/v1/bots/{bot_id}")
        bot = get_response.json()
        assert bot["status"] == "awaiting_stop"

    def test_stop_bot_response_format(self, client: TestClient):
        """Verify stop_bot response format"""
        list_response = client.get("/api/v1/bots/")
        bots = list_response.json()["items"]
        assert len(bots) > 0
        
        bot_id = bots[0]["id"]
        response = client.post(f"/api/v1/bots/{bot_id}/stop")
        assert response.status_code == 200
        
        data = response.json()
        assert "ok" in data
        assert "status" in data
        assert "message" in data
        assert isinstance(data["ok"], bool)

    def test_stop_bot_idempotency(self, client: TestClient, reset_bots):
        """Stopping already-stopped bot should succeed"""
        list_response = client.get("/api/v1/bots/")
        bots = list_response.json()["items"]
        assert len(bots) > 0
        
        bot_id = bots[0]["id"]
        
        # Stop twice
        response1 = client.post(f"/api/v1/bots/{bot_id}/stop")
        response2 = client.post(f"/api/v1/bots/{bot_id}/stop")
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json()["ok"] is True
        assert response2.json()["ok"] is True


class TestDeleteBot:
    """Test POST /api/v1/bots/{bot_id}/delete endpoint"""

    def test_delete_bot_success(self, client: TestClient, reset_bots):
        """Delete bot successfully"""
        # Get initial count
        list_response = client.get("/api/v1/bots/")
        initial_total = list_response.json()["total"]
        bots = list_response.json()["items"]
        assert len(bots) > 0
        
        bot_id = bots[0]["id"]
        
        # Delete the bot
        response = client.post(f"/api/v1/bots/{bot_id}/delete")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "message" in data
        assert "deleted" in data["message"].lower()

    def test_delete_bot_removes_from_list(self, client: TestClient, reset_bots):
        """Deleted bot should not appear in list"""
        # Get bot to delete
        list_response = client.get("/api/v1/bots/")
        initial_total = list_response.json()["total"]
        bots = list_response.json()["items"]
        assert len(bots) > 0
        
        bot_id = bots[0]["id"]
        
        # Delete bot
        delete_response = client.post(f"/api/v1/bots/{bot_id}/delete")
        assert delete_response.status_code == 200
        
        # Verify removed from list
        list_after = client.get("/api/v1/bots/")
        assert list_after.json()["total"] == initial_total - 1
        
        # Verify GET returns 404
        get_response = client.get(f"/api/v1/bots/{bot_id}")
        assert get_response.status_code == 404

    def test_delete_bot_not_found(self, client: TestClient):
        """Delete non-existent bot should return 404"""
        response = client.post("/api/v1/bots/nonexistent_bot/delete")
        assert response.status_code == 404
        
        error = response.json()
        assert "detail" in error
        assert "not found" in error["detail"].lower()

    def test_delete_bot_response_format(self, client: TestClient, reset_bots):
        """Verify delete_bot response format"""
        list_response = client.get("/api/v1/bots/")
        bots = list_response.json()["items"]
        assert len(bots) > 0
        
        bot_id = bots[0]["id"]
        response = client.post(f"/api/v1/bots/{bot_id}/delete")
        assert response.status_code == 200
        
        data = response.json()
        assert "ok" in data
        assert "message" in data
        assert isinstance(data["ok"], bool)
        assert data["status"] is None  # Delete doesn't return status

    def test_delete_bot_idempotency(self, client: TestClient, reset_bots):
        """Deleting already-deleted bot should return 404"""
        list_response = client.get("/api/v1/bots/")
        bots = list_response.json()["items"]
        assert len(bots) > 0
        
        bot_id = bots[0]["id"]
        
        # First delete succeeds
        response1 = client.post(f"/api/v1/bots/{bot_id}/delete")
        assert response1.status_code == 200
        
        # Second delete fails (404)
        response2 = client.post(f"/api/v1/bots/{bot_id}/delete")
        assert response2.status_code == 404


class TestBotEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_bot_special_characters_in_id(self, client: TestClient):
        """Bot IDs with special characters"""
        special_ids = ["bot@123", "bot#456", "bot$789", "bot%abc"]
        
        for bot_id in special_ids:
            response = client.get(f"/api/v1/bots/{bot_id}")
            assert response.status_code == 404

    def test_bot_long_id(self, client: TestClient):
        """Bot with very long ID"""
        long_id = "a" * 1000
        response = client.get(f"/api/v1/bots/{long_id}")
        assert response.status_code == 404

    def test_bot_unicode_id(self, client: TestClient):
        """Bot ID with unicode characters"""
        response = client.get("/api/v1/bots/бот_123")
        assert response.status_code == 404

    def test_multiple_consecutive_actions(self, client: TestClient, reset_bots):
        """Perform multiple actions on same bot"""
        list_response = client.get("/api/v1/bots/")
        bots = list_response.json()["items"]
        assert len(bots) > 0
        
        bot_id = bots[0]["id"]
        
        # Start -> Stop -> Start
        r1 = client.post(f"/api/v1/bots/{bot_id}/start")
        assert r1.status_code == 200
        assert r1.json()["status"] == "awaiting_start"
        
        r2 = client.post(f"/api/v1/bots/{bot_id}/stop")
        assert r2.status_code == 200
        assert r2.json()["status"] == "awaiting_stop"
        
        r3 = client.post(f"/api/v1/bots/{bot_id}/start")
        assert r3.status_code == 200
        assert r3.json()["status"] == "awaiting_start"

    def test_bot_status_values(self, client: TestClient):
        """Verify bot status is one of valid enum values"""
        list_response = client.get("/api/v1/bots/")
        bots = list_response.json()["items"]
        
        valid_statuses = [
            "running",
            "stopped",
            "awaiting_signal",
            "awaiting_start",
            "awaiting_stop",
            "error",
        ]
        
        for bot in bots:
            assert bot["status"] in valid_statuses


class TestBotIntegration:
    """Test integration scenarios and workflows"""

    def test_full_bot_lifecycle(self, client: TestClient, reset_bots):
        """Complete bot lifecycle: list -> get -> start -> stop -> delete"""
        # List bots
        list_response = client.get("/api/v1/bots/")
        assert list_response.status_code == 200
        initial_total = list_response.json()["total"]
        bots = list_response.json()["items"]
        assert len(bots) > 0
        
        bot_id = bots[0]["id"]
        
        # Get specific bot
        get_response = client.get(f"/api/v1/bots/{bot_id}")
        assert get_response.status_code == 200
        bot = get_response.json()
        assert bot["id"] == bot_id
        
        # Start bot
        start_response = client.post(f"/api/v1/bots/{bot_id}/start")
        assert start_response.status_code == 200
        assert start_response.json()["status"] == "awaiting_start"
        
        # Stop bot
        stop_response = client.post(f"/api/v1/bots/{bot_id}/stop")
        assert stop_response.status_code == 200
        assert stop_response.json()["status"] == "awaiting_stop"
        
        # Delete bot
        delete_response = client.post(f"/api/v1/bots/{bot_id}/delete")
        assert delete_response.status_code == 200
        
        # Verify removed
        final_list = client.get("/api/v1/bots/")
        assert final_list.json()["total"] == initial_total - 1

    def test_pagination_consistency_after_delete(self, client: TestClient, reset_bots):
        """Pagination remains consistent after deleting bots"""
        # Get initial state
        list1 = client.get("/api/v1/bots/")
        initial_total = list1.json()["total"]
        
        if initial_total > 1:
            # Delete first bot
            bot_id = list1.json()["items"][0]["id"]
            delete_response = client.post(f"/api/v1/bots/{bot_id}/delete")
            assert delete_response.status_code == 200
            
            # Verify total decreased
            list2 = client.get("/api/v1/bots/")
            assert list2.json()["total"] == initial_total - 1

    def test_concurrent_operations_different_bots(self, client: TestClient, reset_bots):
        """Operate on multiple bots concurrently"""
        list_response = client.get("/api/v1/bots/")
        bots = list_response.json()["items"]
        
        if len(bots) >= 2:
            # Start first bot, stop second bot
            r1 = client.post(f"/api/v1/bots/{bots[0]['id']}/start")
            r2 = client.post(f"/api/v1/bots/{bots[1]['id']}/stop")
            
            assert r1.status_code == 200
            assert r2.status_code == 200
            
            # Verify states
            bot1 = client.get(f"/api/v1/bots/{bots[0]['id']}").json()
            bot2 = client.get(f"/api/v1/bots/{bots[1]['id']}").json()
            
            assert bot1["status"] == "awaiting_start"
            assert bot2["status"] == "awaiting_stop"


class TestResponseFormats:
    """Test response format consistency"""

    def test_list_response_format(self, client: TestClient):
        """Verify list endpoint response format"""
        response = client.get("/api/v1/bots/")
        assert response.status_code == 200
        
        data = response.json()
        assert set(data.keys()) == {"items", "total"}
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)

    def test_action_response_format_consistency(self, client: TestClient):
        """Verify all action endpoints return consistent ActionResponse"""
        list_response = client.get("/api/v1/bots/")
        bots = list_response.json()["items"]
        assert len(bots) > 0
        
        bot_id = bots[0]["id"]
        
        # Start response
        start = client.post(f"/api/v1/bots/{bot_id}/start").json()
        assert "ok" in start
        assert "status" in start
        assert "message" in start
        
        # Stop response
        stop = client.post(f"/api/v1/bots/{bot_id}/stop").json()
        assert "ok" in stop
        assert "status" in stop
        assert "message" in stop

    def test_error_response_format(self, client: TestClient):
        """Verify 404 error response format"""
        response = client.get("/api/v1/bots/nonexistent")
        assert response.status_code == 404
        
        error = response.json()
        assert "detail" in error
        assert isinstance(error["detail"], str)


class TestMockDataSeeding:
    """Test mock data seeding behavior"""

    def test_seed_creates_initial_bots(self, client: TestClient, reset_bots):
        """Seeding creates exactly 3 initial bots"""
        response = client.get("/api/v1/bots/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["total"] == 3  # _seed() creates 3 bots
        assert len(data["items"]) == 3

    def test_seed_idempotency(self, client: TestClient):
        """Seeding is idempotent (doesn't duplicate)"""
        # First call
        response1 = client.get("/api/v1/bots/")
        total1 = response1.json()["total"]
        
        # Second call
        response2 = client.get("/api/v1/bots/")
        total2 = response2.json()["total"]
        
        # Should be same (no duplicates)
        assert total1 == total2

    def test_seed_data_validity(self, client: TestClient):
        """Seeded bots have valid data"""
        response = client.get("/api/v1/bots/")
        bots = response.json()["items"]
        
        assert len(bots) == 3
        
        # Verify each bot has valid fields
        for bot in bots:
            assert bot["id"].startswith("bot_")
            assert len(bot["name"]) > 0
            assert len(bot["strategy"]) > 0
            assert len(bot["symbols"]) > 0
            assert bot["capital_allocated"] > 0
            assert bot["status"] in [
                "running",
                "stopped",
                "awaiting_signal",
                "awaiting_start",
                "awaiting_stop",
                "error",
            ]

    def test_seed_data_specific_values(self, client: TestClient, reset_bots):
        """Verify specific seeded bot values"""
        response = client.get("/api/v1/bots/")
        bots = response.json()["items"]
        
        # Find bot_1
        bot_1 = next((b for b in bots if b["id"] == "bot_1"), None)
        assert bot_1 is not None
        assert bot_1["name"] == "BTC Scalper"
        assert bot_1["strategy"] == "scalper_v1"
        assert "BTCUSDT" in bot_1["symbols"]
        assert bot_1["capital_allocated"] == 1000.0
        assert bot_1["status"] == "running"
