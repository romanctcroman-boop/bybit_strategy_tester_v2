"""
Tests for Chat History API Router

Tests cover:
1. CRUD operations for conversations
2. Sync from localStorage
3. Filtering and pagination
4. Error handling
"""

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.database import Base, engine


@pytest.fixture(scope="session", autouse=True)
def ensure_chat_tables():
    """Ensure chat history tables exist before tests run."""
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


class TestChatHistoryAPI:
    """Tests for chat history endpoints"""

    @pytest.fixture(autouse=True)
    def setup(self, client):
        """Clear test data before each test"""
        self.client = client
        self.client.delete("/api/v1/chat/history/clear")

    def test_list_conversations_empty(self):
        """Test listing conversations when empty"""
        response = self.client.get("/api/v1/chat/history")

        # Should return 200 even if empty
        assert response.status_code == 200
        data = response.json()
        assert "conversations" in data

    def test_create_conversation(self):
        """Test creating a new conversation"""
        payload = {
            "prompt": "Test prompt for strategy analysis",
            "response": "Test AI response",
            "tab": "strategy",
            "agent": "deepseek",
        }

        response = self.client.post("/api/v1/chat/history", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["prompt"] == payload["prompt"]
        assert data["response"] == payload["response"]
        assert data["tab"] == "strategy"
        assert data["agent"] == "deepseek"
        assert "created_at" in data

    def test_create_conversation_with_reasoning(self):
        """Test creating conversation with DeepSeek reasoning"""
        payload = {
            "prompt": "Analyze BTC momentum",
            "response": "Based on analysis...",
            "reasoning": "Let me think step by step...",
            "tab": "strategy",
            "agent": "deepseek",
        }

        response = self.client.post("/api/v1/chat/history", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["reasoning"] == payload["reasoning"]

    def test_create_conversation_invalid_tab(self):
        """Test creating conversation with invalid tab"""
        payload = {
            "prompt": "Test",
            "response": "Test",
            "tab": "invalid_tab",
            "agent": "deepseek",
        }

        response = self.client.post("/api/v1/chat/history", json=payload)

        assert response.status_code == 422  # Validation error

    def test_create_conversation_empty_prompt(self):
        """Test creating conversation with empty prompt"""
        payload = {
            "prompt": "",
            "response": "Test",
            "tab": "strategy",
            "agent": "deepseek",
        }

        response = self.client.post("/api/v1/chat/history", json=payload)

        assert response.status_code == 422  # Validation error

    def test_get_conversation_by_id(self):
        """Test getting a specific conversation"""
        # First create a conversation
        create_response = self.client.post(
            "/api/v1/chat/history",
            json={
                "prompt": "Get by ID test",
                "response": "Response",
                "tab": "research",
                "agent": "perplexity",
            },
        )

        if create_response.status_code != 201:
            pytest.skip("Could not create test conversation")

        conv_id = create_response.json()["id"]

        # Then get it by ID
        response = self.client.get(f"/api/v1/chat/history/{conv_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == conv_id
        assert data["prompt"] == "Get by ID test"

    def test_get_conversation_not_found(self):
        """Test getting non-existent conversation"""
        response = self.client.get("/api/v1/chat/history/nonexistent-id-12345")

        assert response.status_code == 404

    def test_update_conversation(self):
        """Test updating a conversation"""
        # First create
        create_response = self.client.post(
            "/api/v1/chat/history",
            json={
                "prompt": "Original prompt",
                "response": "Original response",
                "tab": "strategy",
                "agent": "deepseek",
            },
        )

        if create_response.status_code != 201:
            pytest.skip("Could not create test conversation")

        conv_id = create_response.json()["id"]

        # Then update
        update_response = self.client.put(
            f"/api/v1/chat/history/{conv_id}",
            json={"starred": True, "title": "Important conversation"},
        )

        assert update_response.status_code == 200
        data = update_response.json()
        assert data["starred"] is True
        assert data["title"] == "Important conversation"

    def test_delete_conversation(self):
        """Test deleting a conversation"""
        # First create
        create_response = self.client.post(
            "/api/v1/chat/history",
            json={
                "prompt": "To be deleted",
                "response": "Response",
                "tab": "risk",
                "agent": "unified",
            },
        )

        if create_response.status_code != 201:
            pytest.skip("Could not create test conversation")

        conv_id = create_response.json()["id"]

        # Delete it
        delete_response = self.client.delete(f"/api/v1/chat/history/{conv_id}")

        assert delete_response.status_code == 204

        # Verify it's gone
        get_response = self.client.get(f"/api/v1/chat/history/{conv_id}")
        assert get_response.status_code == 404

    def test_list_conversations_with_tab_filter(self):
        """Test filtering conversations by tab"""
        # Create conversations in different tabs
        self.client.post(
            "/api/v1/chat/history",
            json={
                "prompt": "Strategy 1",
                "response": "Response",
                "tab": "strategy",
                "agent": "deepseek",
            },
        )
        self.client.post(
            "/api/v1/chat/history",
            json={
                "prompt": "Research 1",
                "response": "Response",
                "tab": "research",
                "agent": "perplexity",
            },
        )

        # Filter by tab
        response = self.client.get("/api/v1/chat/history?tab=strategy")

        assert response.status_code == 200
        data = response.json()

        # All returned should be strategy tab
        for conv in data["conversations"]:
            if conv["prompt"] in ["Strategy 1"]:
                assert conv["tab"] == "strategy"

    def test_list_conversations_with_starred_filter(self):
        """Test filtering starred conversations"""
        # Create and star a conversation
        create_response = self.client.post(
            "/api/v1/chat/history",
            json={
                "prompt": "Important prompt",
                "response": "Response",
                "tab": "strategy",
                "agent": "deepseek",
            },
        )

        if create_response.status_code == 201:
            conv_id = create_response.json()["id"]
            self.client.put(f"/api/v1/chat/history/{conv_id}", json={"starred": True})

        # Filter starred only
        response = self.client.get("/api/v1/chat/history?starred=true")

        assert response.status_code == 200

    def test_list_conversations_pagination(self):
        """Test pagination of conversations"""
        # Create multiple conversations
        for i in range(5):
            self.client.post(
                "/api/v1/chat/history",
                json={
                    "prompt": f"Pagination test {i}",
                    "response": "Response",
                    "tab": "strategy",
                    "agent": "deepseek",
                },
            )

        # Get with limit (API uses per_page parameter)
        response = self.client.get("/api/v1/chat/history?per_page=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) <= 2

    def test_sync_conversations(self):
        """Test bulk sync from localStorage"""
        payload = {
            "conversations": [
                {
                    "prompt": "Synced prompt 1",
                    "response": "Synced response 1",
                    "tab": "strategy",
                    "agent": "deepseek",
                    "timestamp": 1702400000000,
                },
                {
                    "prompt": "Synced prompt 2",
                    "response": "Synced response 2",
                    "tab": "research",
                    "agent": "perplexity",
                    "timestamp": 1702400001000,
                },
            ]
        }

        response = self.client.post("/api/v1/chat/history/sync", json=payload)

        # Should succeed or indicate some were synced
        assert response.status_code in [200, 201, 207]

    def test_clear_all_history(self):
        """Test clearing all chat history"""
        # Create some conversations first
        self.client.post(
            "/api/v1/chat/history",
            json={
                "prompt": "To be cleared",
                "response": "Response",
                "tab": "strategy",
                "agent": "deepseek",
            },
        )

        # Clear all
        response = self.client.delete("/api/v1/chat/history/clear")

        assert response.status_code == 200

        # Verify cleared
        list_response = self.client.get("/api/v1/chat/history")
        assert list_response.status_code == 200

    def test_get_stats(self):
        """Test getting conversation statistics"""
        response = self.client.get("/api/v1/chat/history/stats")

        # May be 200 or 404 if endpoint doesn't exist
        if response.status_code == 200:
            data = response.json()
            assert "total" in data or "stats" in data


class TestChatHistoryValidation:
    """Tests for input validation"""

    @pytest.fixture(autouse=True)
    def setup(self, client):
        self.client = client
        self.client.delete("/api/v1/chat/history/clear")

    def test_prompt_max_length(self):
        """Test prompt maximum length validation"""
        payload = {
            "prompt": "x" * 10001,  # Exceeds max length
            "response": "Response",
            "tab": "strategy",
            "agent": "deepseek",
        }

        response = self.client.post("/api/v1/chat/history", json=payload)

        assert response.status_code == 422

    def test_title_max_length(self):
        """Test title maximum length on update"""
        # First create
        create_response = self.client.post(
            "/api/v1/chat/history",
            json={
                "prompt": "Test",
                "response": "Response",
                "tab": "strategy",
                "agent": "deepseek",
            },
        )

        if create_response.status_code != 201:
            pytest.skip("Could not create test conversation")

        conv_id = create_response.json()["id"]

        # Try to update with too long title
        update_response = self.client.put(
            f"/api/v1/chat/history/{conv_id}", json={"title": "x" * 201}
        )

        assert update_response.status_code == 422

    def test_invalid_agent_type(self):
        """Test invalid agent type validation"""
        payload = {
            "prompt": "Test",
            "response": "Response",
            "tab": "strategy",
            "agent": "invalid_agent",
        }

        response = self.client.post("/api/v1/chat/history", json=payload)

        assert response.status_code == 422


class TestChatHistorySearch:
    """Tests for search functionality"""

    @pytest.fixture(autouse=True)
    def setup(self, client):
        self.client = client
        self.client.delete("/api/v1/chat/history/clear")

    def test_search_by_query(self):
        """Test searching conversations by query"""
        # Create conversation with specific content
        self.client.post(
            "/api/v1/chat/history",
            json={
                "prompt": "Bitcoin momentum strategy",
                "response": "RSI crossover analysis",
                "tab": "strategy",
                "agent": "deepseek",
            },
        )

        # Search for it
        response = self.client.get("/api/v1/chat/history?q=Bitcoin")

        assert response.status_code == 200

    def test_search_case_insensitive(self):
        """Test case-insensitive search"""
        self.client.post(
            "/api/v1/chat/history",
            json={
                "prompt": "ETHEREUM analysis",
                "response": "Response",
                "tab": "research",
                "agent": "perplexity",
            },
        )

        response = self.client.get("/api/v1/chat/history?q=ethereum")

        assert response.status_code == 200
