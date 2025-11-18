"""
Comprehensive tests for active_deals.py router.

Week 7 Day 2: Target 95-100% coverage from current 90%
Missing coverage: lines 85, 103->106, 111-115
"""
import pytest
from fastapi.testclient import TestClient
from backend.api.app import app


@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)


@pytest.fixture
def reset_deals():
    """Reset deals state between tests"""
    from backend.api.routers import active_deals
    
    # Clear deals
    active_deals._DEALS.clear()
    yield
    # Clear after test
    active_deals._DEALS.clear()


class TestListActiveDeals:
    """Test GET /api/v1/active-deals endpoint"""
    
    def test_list_deals_default_pagination(self, client: TestClient):
        """List deals with default limit/offset"""
        response = client.get("/api/v1/active-deals")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
    
    def test_list_deals_seeded_data(self, client: TestClient):
        """Verify seeded mock data"""
        response = client.get("/api/v1/active-deals")
        data = response.json()
        
        # Should have 2 mock deals
        assert data["total"] == 2
        assert len(data["items"]) == 2
    
    def test_list_deals_with_limit(self, client: TestClient):
        """Test limit parameter"""
        response = client.get("/api/v1/active-deals?limit=1")
        data = response.json()
        
        assert response.status_code == 200
        assert len(data["items"]) == 1
        assert data["total"] == 2  # Total unchanged
    
    def test_list_deals_with_offset(self, client: TestClient):
        """Test offset parameter"""
        # Get first deal
        response1 = client.get("/api/v1/active-deals?limit=1&offset=0")
        data1 = response1.json()
        
        # Get second deal
        response2 = client.get("/api/v1/active-deals?limit=1&offset=1")
        data2 = response2.json()
        
        assert len(data1["items"]) == 1
        assert len(data2["items"]) == 1
        assert data1["items"][0]["id"] != data2["items"][0]["id"]
    
    def test_list_deals_offset_beyond_total(self, client: TestClient):
        """Offset beyond total returns empty items"""
        response = client.get("/api/v1/active-deals?limit=10&offset=100")
        data = response.json()
        
        assert response.status_code == 200
        assert data["items"] == []
        assert data["total"] == 2
    
    def test_list_deals_limit_validation_minimum(self, client: TestClient):
        """Limit must be >= 1"""
        response = client.get("/api/v1/active-deals?limit=0")
        
        # FastAPI validation should reject
        assert response.status_code == 422
    
    def test_list_deals_limit_validation_maximum(self, client: TestClient):
        """Limit must be <= 500"""
        response = client.get("/api/v1/active-deals?limit=501")
        
        # FastAPI validation should reject
        assert response.status_code == 422
    
    def test_list_deals_offset_validation(self, client: TestClient):
        """Offset must be >= 0"""
        response = client.get("/api/v1/active-deals?offset=-1")
        
        # FastAPI validation should reject
        assert response.status_code == 422
    
    def test_list_deals_large_limit(self, client: TestClient):
        """Large limit within bounds"""
        response = client.get("/api/v1/active-deals?limit=500")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 500
    
    def test_list_deals_structure(self, client: TestClient):
        """Verify deal structure"""
        response = client.get("/api/v1/active-deals")
        data = response.json()
        
        deal = data["items"][0]
        
        # Check required fields
        assert "id" in deal
        assert "bot_id" in deal
        assert "symbol" in deal
        assert "entry_price" in deal
        assert "quantity" in deal
        assert "next_open_price" in deal
        assert "current_price" in deal
        assert "pnl_abs" in deal
        assert "pnl_pct" in deal
        assert "opened_at" in deal
    
    def test_list_deals_field_types(self, client: TestClient):
        """Verify field types"""
        response = client.get("/api/v1/active-deals")
        data = response.json()
        
        deal = data["items"][0]
        
        assert isinstance(deal["id"], str)
        assert isinstance(deal["bot_id"], str)
        assert isinstance(deal["symbol"], str)
        assert isinstance(deal["entry_price"], (int, float))
        assert isinstance(deal["quantity"], (int, float))
        assert isinstance(deal["pnl_abs"], (int, float))
        assert isinstance(deal["pnl_pct"], (int, float))


class TestCloseDeal:
    """Test POST /api/v1/active-deals/{deal_id}/close endpoint"""
    
    def test_close_deal_success(self, client: TestClient):
        """Close an existing deal"""
        # Get a deal ID
        response = client.get("/api/v1/active-deals")
        deals = response.json()["items"]
        deal_id = deals[0]["id"]
        
        # Close the deal
        response = client.post(f"/api/v1/active-deals/{deal_id}/close")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert data["action"] == "close"
        assert "message" in data
    
    def test_close_deal_removes_from_list(self, client: TestClient, reset_deals):
        """Closed deal should be removed from active list"""
        # Get initial deals
        response = client.get("/api/v1/active-deals")
        initial_deals = response.json()["items"]
        initial_total = len(initial_deals)
        deal_id = initial_deals[0]["id"]
        
        # Close the deal
        client.post(f"/api/v1/active-deals/{deal_id}/close")
        
        # Verify it's gone
        response = client.get("/api/v1/active-deals")
        remaining_deals = response.json()["items"]
        
        assert len(remaining_deals) == initial_total - 1
        assert deal_id not in [d["id"] for d in remaining_deals]
    
    def test_close_nonexistent_deal(self, client: TestClient):
        """Closing non-existent deal returns 404"""
        response = client.post("/api/v1/active-deals/nonexistent_id/close")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert data["detail"] == "Deal not found"
    
    def test_close_already_closed_deal(self, client: TestClient):
        """Closing already closed deal returns 404"""
        # Get and close a deal
        response = client.get("/api/v1/active-deals")
        deal_id = response.json()["items"][0]["id"]
        client.post(f"/api/v1/active-deals/{deal_id}/close")
        
        # Try to close again
        response = client.post(f"/api/v1/active-deals/{deal_id}/close")
        
        assert response.status_code == 404
    
    def test_close_deal_response_format(self, client: TestClient):
        """Verify response format"""
        response = client.get("/api/v1/active-deals")
        deal_id = response.json()["items"][0]["id"]
        
        response = client.post(f"/api/v1/active-deals/{deal_id}/close")
        data = response.json()
        
        assert "ok" in data
        assert "action" in data
        assert "message" in data
        assert isinstance(data["ok"], bool)
        assert isinstance(data["action"], str)


class TestAverageDeal:
    """Test POST /api/v1/active-deals/{deal_id}/average endpoint"""
    
    def test_average_deal_success(self, client: TestClient):
        """Average an existing deal"""
        # Get a deal ID
        response = client.get("/api/v1/active-deals")
        deals = response.json()["items"]
        deal_id = deals[0]["id"]
        
        # Average the deal
        response = client.post(f"/api/v1/active-deals/{deal_id}/average")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert data["action"] == "average"
        assert "message" in data
    
    def test_average_deal_adjusts_entry_price(self, client: TestClient):
        """Averaging should adjust entry price"""
        # Get deal with current_price
        response = client.get("/api/v1/active-deals")
        deals = response.json()["items"]
        
        # Find deal with current_price
        deal = next(d for d in deals if d["current_price"] is not None)
        deal_id = deal["id"]
        original_entry = deal["entry_price"]
        current_price = deal["current_price"]
        
        # Average the deal
        client.post(f"/api/v1/active-deals/{deal_id}/average")
        
        # Get updated deal
        response = client.get("/api/v1/active-deals")
        updated_deal = next(d for d in response.json()["items"] if d["id"] == deal_id)
        
        # Entry price should be average of original and current
        expected_avg = round((original_entry + current_price) / 2, 4)
        assert updated_deal["entry_price"] == expected_avg
    
    def test_average_deal_with_null_current_price(self, client: TestClient, reset_deals):
        """Averaging deal with null current_price"""
        from backend.api.routers import active_deals
        from datetime import datetime, UTC
        
        # Create deal with null current_price
        test_deal = active_deals.ActiveDeal(
            id="test_null",
            bot_id="bot_test",
            symbol="TESTUSDT",
            entry_price=100.0,
            quantity=1.0,
            next_open_price=101.0,
            current_price=None,  # Null price
            pnl_abs=0.0,
            pnl_pct=0.0,
            opened_at=datetime.now(UTC)
        )
        active_deals._DEALS["test_null"] = test_deal
        
        # Average the deal
        response = client.post("/api/v1/active-deals/test_null/average")
        
        assert response.status_code == 200
        assert response.json()["ok"] is True
        
        # Entry price should remain unchanged
        updated = client.get("/api/v1/active-deals").json()["items"]
        updated_deal = next(d for d in updated if d["id"] == "test_null")
        assert updated_deal["entry_price"] == 100.0  # Unchanged
    
    def test_average_nonexistent_deal(self, client: TestClient):
        """Averaging non-existent deal returns 404"""
        response = client.post("/api/v1/active-deals/nonexistent_id/average")
        
        assert response.status_code == 404
        assert response.json()["detail"] == "Deal not found"
    
    def test_average_deal_response_format(self, client: TestClient):
        """Verify response format"""
        response = client.get("/api/v1/active-deals")
        deal_id = response.json()["items"][0]["id"]
        
        response = client.post(f"/api/v1/active-deals/{deal_id}/average")
        data = response.json()
        
        assert "ok" in data
        assert "action" in data
        assert "message" in data
        assert data["action"] == "average"
    
    def test_average_deal_remains_active(self, client: TestClient):
        """Averaged deal should remain in active list"""
        # Get initial count
        response = client.get("/api/v1/active-deals")
        initial_count = response.json()["total"]
        deal_id = response.json()["items"][0]["id"]
        
        # Average the deal
        client.post(f"/api/v1/active-deals/{deal_id}/average")
        
        # Count should remain same
        response = client.get("/api/v1/active-deals")
        assert response.json()["total"] == initial_count


class TestCancelDeal:
    """Test POST /api/v1/active-deals/{deal_id}/cancel endpoint"""
    
    def test_cancel_deal_success(self, client: TestClient):
        """Cancel an existing deal"""
        # Get a deal ID
        response = client.get("/api/v1/active-deals")
        deals = response.json()["items"]
        deal_id = deals[0]["id"]
        
        # Cancel the deal
        response = client.post(f"/api/v1/active-deals/{deal_id}/cancel")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert data["action"] == "cancel"
        assert "message" in data
    
    def test_cancel_deal_removes_from_list(self, client: TestClient, reset_deals):
        """Cancelled deal should be removed from active list"""
        # Get initial deals
        response = client.get("/api/v1/active-deals")
        initial_deals = response.json()["items"]
        initial_total = len(initial_deals)
        deal_id = initial_deals[0]["id"]
        
        # Cancel the deal
        client.post(f"/api/v1/active-deals/{deal_id}/cancel")
        
        # Verify it's gone
        response = client.get("/api/v1/active-deals")
        remaining_deals = response.json()["items"]
        
        assert len(remaining_deals) == initial_total - 1
        assert deal_id not in [d["id"] for d in remaining_deals]
    
    def test_cancel_nonexistent_deal(self, client: TestClient):
        """Cancelling non-existent deal returns 404"""
        response = client.post("/api/v1/active-deals/nonexistent_id/cancel")
        
        assert response.status_code == 404
        assert response.json()["detail"] == "Deal not found"
    
    def test_cancel_already_cancelled_deal(self, client: TestClient):
        """Cancelling already cancelled deal returns 404"""
        # Get and cancel a deal
        response = client.get("/api/v1/active-deals")
        deal_id = response.json()["items"][0]["id"]
        client.post(f"/api/v1/active-deals/{deal_id}/cancel")
        
        # Try to cancel again
        response = client.post(f"/api/v1/active-deals/{deal_id}/cancel")
        
        assert response.status_code == 404
    
    def test_cancel_deal_response_format(self, client: TestClient):
        """Verify response format"""
        response = client.get("/api/v1/active-deals")
        deal_id = response.json()["items"][0]["id"]
        
        response = client.post(f"/api/v1/active-deals/{deal_id}/cancel")
        data = response.json()
        
        assert "ok" in data
        assert "action" in data
        assert "message" in data
        assert data["action"] == "cancel"


class TestDealEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_empty_deal_id(self, client: TestClient):
        """Empty deal ID should be handled"""
        # FastAPI path validation handles this
        response = client.post("/api/v1/active-deals//close")
        # Will match different route or 404
        assert response.status_code in [404, 307]  # Redirect or not found
    
    def test_special_characters_in_deal_id(self, client: TestClient):
        """Deal ID with special characters"""
        response = client.post("/api/v1/active-deals/deal%20with%20spaces/close")
        
        assert response.status_code == 404
        assert response.json()["detail"] == "Deal not found"
    
    def test_very_long_deal_id(self, client: TestClient):
        """Very long deal ID"""
        long_id = "x" * 1000
        response = client.post(f"/api/v1/active-deals/{long_id}/close")
        
        assert response.status_code == 404
    
    def test_numeric_deal_id(self, client: TestClient):
        """Numeric deal ID (should work as string)"""
        response = client.post("/api/v1/active-deals/12345/close")
        
        assert response.status_code == 404
    
    def test_multiple_actions_same_deal(self, client: TestClient):
        """Multiple actions on same deal"""
        response = client.get("/api/v1/active-deals")
        deal_id = response.json()["items"][0]["id"]
        
        # Average then close
        avg_response = client.post(f"/api/v1/active-deals/{deal_id}/average")
        assert avg_response.status_code == 200
        
        close_response = client.post(f"/api/v1/active-deals/{deal_id}/close")
        assert close_response.status_code == 200
        
        # Now deal should be gone
        cancel_response = client.post(f"/api/v1/active-deals/{deal_id}/cancel")
        assert cancel_response.status_code == 404


class TestDealIntegration:
    """Test integration scenarios"""
    
    def test_full_deal_lifecycle(self, client: TestClient, reset_deals):
        """Complete deal lifecycle: list → average → close"""
        # Step 1: List deals
        response = client.get("/api/v1/active-deals")
        assert response.status_code == 200
        initial_total = response.json()["total"]
        deal_id = response.json()["items"][0]["id"]
        
        # Step 2: Average the position
        avg_response = client.post(f"/api/v1/active-deals/{deal_id}/average")
        assert avg_response.status_code == 200
        assert avg_response.json()["action"] == "average"
        
        # Step 3: Verify still in list
        response = client.get("/api/v1/active-deals")
        assert response.json()["total"] == initial_total
        
        # Step 4: Close the deal
        close_response = client.post(f"/api/v1/active-deals/{deal_id}/close")
        assert close_response.status_code == 200
        
        # Step 5: Verify removed
        response = client.get("/api/v1/active-deals")
        assert response.json()["total"] == initial_total - 1
    
    def test_pagination_consistency(self, client: TestClient):
        """Pagination should be consistent"""
        # Get all deals
        all_response = client.get("/api/v1/active-deals?limit=100")
        all_deals = all_response.json()["items"]
        
        # Get in chunks
        chunk1 = client.get("/api/v1/active-deals?limit=1&offset=0").json()["items"]
        chunk2 = client.get("/api/v1/active-deals?limit=1&offset=1").json()["items"]
        
        combined = chunk1 + chunk2
        
        # Should match first 2 from all_deals
        assert combined[0]["id"] == all_deals[0]["id"]
        assert combined[1]["id"] == all_deals[1]["id"]
    
    def test_concurrent_operations(self, client: TestClient):
        """Simulate concurrent operations"""
        # Get two different deals
        response = client.get("/api/v1/active-deals")
        deals = response.json()["items"]
        
        if len(deals) >= 2:
            deal1_id = deals[0]["id"]
            deal2_id = deals[1]["id"]
            
            # Average deal1, close deal2
            avg_response = client.post(f"/api/v1/active-deals/{deal1_id}/average")
            close_response = client.post(f"/api/v1/active-deals/{deal2_id}/close")
            
            assert avg_response.status_code == 200
            assert close_response.status_code == 200
            
            # Verify state
            response = client.get("/api/v1/active-deals")
            remaining_ids = [d["id"] for d in response.json()["items"]]
            
            assert deal1_id in remaining_ids  # Averaged, still active
            assert deal2_id not in remaining_ids  # Closed, removed


class TestResponseFormats:
    """Test response format consistency"""
    
    def test_list_response_format(self, client: TestClient):
        """List endpoint should return consistent format"""
        response = client.get("/api/v1/active-deals")
        data = response.json()
        
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
        assert data["total"] >= len(data["items"])
    
    def test_action_response_format_consistency(self, client: TestClient):
        """All action endpoints should return same format"""
        response = client.get("/api/v1/active-deals")
        deals = response.json()["items"]
        
        # Need at least 3 deals for this test
        if len(deals) >= 3:
            # Test each action
            close_resp = client.post(f"/api/v1/active-deals/{deals[0]['id']}/close")
            avg_resp = client.post(f"/api/v1/active-deals/{deals[1]['id']}/average")
            cancel_resp = client.post(f"/api/v1/active-deals/{deals[2]['id']}/cancel")
            
            # All should have same structure
            for resp in [close_resp, avg_resp, cancel_resp]:
                data = resp.json()
                assert "ok" in data
                assert "action" in data
                assert "message" in data
                assert isinstance(data["ok"], bool)
                assert isinstance(data["action"], str)
    
    def test_error_response_format(self, client: TestClient):
        """Error responses should be consistent"""
        response = client.post("/api/v1/active-deals/nonexistent/close")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], str)


class TestMockDataSeeding:
    """Test mock data seeding behavior"""
    
    def test_seed_creates_initial_deals(self, client: TestClient, reset_deals):
        """Seeding should create initial deals"""
        # First call should seed
        response = client.get("/api/v1/active-deals")
        
        assert response.json()["total"] >= 2
    
    def test_seed_idempotent(self, client: TestClient):
        """Multiple calls shouldn't duplicate deals"""
        # Call twice
        response1 = client.get("/api/v1/active-deals")
        response2 = client.get("/api/v1/active-deals")
        
        assert response1.json()["total"] == response2.json()["total"]
    
    def test_seeded_deals_have_valid_data(self, client: TestClient):
        """Seeded deals should have valid data"""
        response = client.get("/api/v1/active-deals")
        deals = response.json()["items"]
        
        for deal in deals:
            assert deal["id"]
            assert deal["bot_id"]
            assert deal["symbol"]
            assert deal["entry_price"] > 0
            assert deal["quantity"] > 0
            assert deal["opened_at"]
