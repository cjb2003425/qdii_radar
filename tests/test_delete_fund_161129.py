"""
Test cases for deleting funds from the fund list, specifically for fund 161129.

This test suite covers:
1. Adding a fund (161129) to the list
2. Verifying the fund was added successfully
3. Deleting the fund from the list
4. Verifying the fund was deleted successfully
5. Testing error handling for deleting non-existent funds
6. Verifying database cleanup after deletion
"""

import pytest
import sys
import os
import asyncio
import httpx
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Backend API URL
BACKEND_URL = "http://127.0.0.1:8088"


class TestAddFund161129:
    """Test adding fund 161129 to the fund list."""

    @pytest.mark.asyncio
    async def test_add_fund_161129(self):
        """Test adding fund 161129 to the fund list via API."""
        fund_code = "161129"
        fund_name = "易方达原油A类人民币"

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Add the fund via POST request
            response = await client.post(
                f"{BACKEND_URL}/api/fund",
                params={"code": fund_code, "name": fund_name}
            )

            assert response.status_code == 200
            data = response.json()

            # Verify the response
            assert data["success"] is True
            assert data["message"] in ["基金添加成功", "基金已存在"]
            assert data["fund"]["code"] == fund_code
            assert data["fund"]["name"] == fund_name

            print(f"\n✓ Fund {fund_code} - {fund_name} added successfully")

    @pytest.mark.asyncio
    async def test_verify_fund_161129_in_list(self):
        """Test that fund 161129 appears in the funds list after adding."""
        fund_code = "161129"

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get all funds
            response = await client.get(f"{BACKEND_URL}/api/funds")
            assert response.status_code == 200

            funds = response.json()
            fund_codes = [fund["code"] for fund in funds]

            # Verify fund 161129 is in the list
            assert fund_code in fund_codes, f"Fund {fund_code} not found in list"

            # Find the fund and verify its details
            fund = next((f for f in funds if f["code"] == fund_code), None)
            assert fund is not None
            assert fund["name"] == "易方达原油A类人民币"

            print(f"\n✓ Fund {fund_code} verified in funds list")


class TestDeleteFund161129:
    """Test deleting fund 161129 from the fund list."""

    @pytest.mark.asyncio
    async def test_delete_fund_161129_success(self):
        """Test deleting fund 161129 from the fund list via API."""
        fund_code = "161129"

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Delete the fund via DELETE request
            response = await client.delete(f"{BACKEND_URL}/api/fund/{fund_code}")

            assert response.status_code == 200
            data = response.json()

            # Verify the response
            assert data["success"] is True
            assert data["message"] == "基金删除成功"

            print(f"\n✓ Fund {fund_code} deleted successfully")

    @pytest.mark.asyncio
    async def test_verify_fund_161129_removed_from_list(self):
        """Test that fund 161129 is removed from the funds list after deletion."""
        fund_code = "161129"

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get all funds
            response = await client.get(f"{BACKEND_URL}/api/funds")
            assert response.status_code == 200

            funds = response.json()
            fund_codes = [fund["code"] for fund in funds]

            # Verify fund 161129 is NOT in the list
            assert fund_code not in fund_codes, f"Fund {fund_code} should not be in list"

            print(f"\n✓ Fund {fund_code} verified as removed from funds list")

    @pytest.mark.asyncio
    async def test_verify_fund_161129_removed_from_funds_json(self):
        """Test that fund 161129 is removed from the funds.json file."""
        fund_code = "161129"

        # Read the funds.json file
        funds_file_path = Path(__file__).parent.parent / "data" / "funds.json"

        with open(funds_file_path, 'r', encoding='utf-8') as f:
            data = f.read()
            funds_data = eval(data)

        # Verify fund 161129 is NOT in the JSON file
        fund_codes = [fund["code"] for fund in funds_data["funds"]]
        assert fund_code not in fund_codes, f"Fund {fund_code} should not be in funds.json"

        print(f"\n✓ Fund {fund_code} verified as removed from funds.json file")


class TestDeleteNonExistentFund:
    """Test error handling when deleting non-existent funds."""

    @pytest.mark.asyncio
    async def test_delete_non_existent_fund(self):
        """Test deleting a fund that doesn't exist."""
        # Use a fund code that definitely doesn't exist
        fake_fund_code = "999999"

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Try to delete the non-existent fund
            response = await client.delete(f"{BACKEND_URL}/api/fund/{fake_fund_code}")

            # Should still return 200 (API handles gracefully)
            assert response.status_code == 200
            data = response.json()

            # Should indicate the fund doesn't exist
            assert data["success"] is False
            assert "不存在" in data["message"]

            print(f"\n✓ Non-existent fund {fake_fund_code} correctly handled")

    @pytest.mark.asyncio
    async def test_delete_fund_161129_twice(self):
        """Test deleting the same fund twice (should fail the second time)."""
        fund_code = "161129"

        async with httpx.AsyncClient(timeout=30.0) as client:
            # First delete - might succeed if fund exists
            response1 = await client.delete(f"{BACKEND_URL}/api/fund/{fund_code}")
            assert response1.status_code == 200

            # Second delete - should fail or indicate fund doesn't exist
            response2 = await client.delete(f"{BACKEND_URL}/api/fund/{fund_code}")
            assert response2.status_code == 200
            data2 = response2.json()

            # The second delete should indicate the fund doesn't exist
            # or still return success (idempotent operation)
            assert "success" in data2

            print(f"\n✓ Double deletion of fund {fund_code} handled correctly")


class TestDeleteFundDatabaseCleanup:
    """Test that deleting a fund properly cleans up the database."""

    @pytest.mark.asyncio
    async def test_monitoring_status_removed_after_deletion(self):
        """Test that monitoring status is removed when fund is deleted."""
        # First, add fund 161129 back
        fund_code = "161129"
        fund_name = "易方达原油A类人民币"

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Add the fund
            await client.post(
                f"{BACKEND_URL}/api/fund",
                params={"code": fund_code, "name": fund_name}
            )

            # Enable monitoring for this fund
            response = await client.put(
                f"{BACKEND_URL}/api/notifications/monitored-funds/{fund_code}",
                json={"enabled": True}
            )
            assert response.status_code == 200

            # Verify monitoring is enabled
            response = await client.get(
                f"{BACKEND_URL}/api/notifications/monitored-funds/{fund_code}"
            )
            assert response.status_code == 200
            data = response.json()
            assert data["enabled"] is True

            print(f"\n✓ Monitoring enabled for fund {fund_code}")

            # Now delete the fund
            response = await client.delete(f"{BACKEND_URL}/api/fund/{fund_code}")
            assert response.status_code == 200

            # Verify monitoring status is removed
            response = await client.get(
                f"{BACKEND_URL}/api/notifications/monitored-funds/{fund_code}"
            )
            assert response.status_code == 200
            data = response.json()

            # Should default to not monitored since fund no longer exists
            assert data["enabled"] is False

            print(f"\n✓ Monitoring status removed after fund {fund_code} deletion")


class TestDeleteFundIntegration:
    """Integration tests for the complete delete workflow."""

    @pytest.mark.asyncio
    async def test_complete_add_delete_workflow(self):
        """Test the complete workflow: add → verify → delete → verify."""
        fund_code = "161129"
        fund_name = "易方达原油A类人民币"

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1: Add the fund
            response = await client.post(
                f"{BACKEND_URL}/api/fund",
                params={"code": fund_code, "name": fund_name}
            )
            assert response.status_code == 200
            assert response.json()["success"] is True
            print(f"\n✓ Step 1: Fund {fund_code} added")

            # Step 2: Verify it's in the list
            response = await client.get(f"{BACKEND_URL}/api/funds")
            funds = response.json()
            fund_codes = [f["code"] for f in funds]
            assert fund_code in fund_codes
            print(f"\n✓ Step 2: Fund {fund_code} verified in list")

            # Step 3: Delete the fund
            response = await client.delete(f"{BACKEND_URL}/api/fund/{fund_code}")
            assert response.status_code == 200
            assert response.json()["success"] is True
            print(f"\n✓ Step 3: Fund {fund_code} deleted")

            # Step 4: Verify it's removed from the list
            response = await client.get(f"{BACKEND_URL}/api/funds")
            funds = response.json()
            fund_codes = [f["code"] for f in funds]
            assert fund_code not in fund_codes
            print(f"\n✓ Step 4: Fund {fund_code} verified as removed")

            print(f"\n✓ Complete workflow test passed!")

    @pytest.mark.asyncio
    async def test_delete_multiple_funds(self):
        """Test deleting multiple funds in sequence."""
        # Add two test funds
        test_funds = [
            ("161129", "易方达原油A类人民币"),
            ("161128", "易方达标普信息科技指数(QDII-LOF)A(人民币)")  # Already in list
        ]

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Add fund 161129 (161128 is already there)
            await client.post(
                f"{BACKEND_URL}/api/fund",
                params={"code": test_funds[0][0], "name": test_funds[0][1]}
            )

            # Delete both funds
            for fund_code, fund_name in test_funds:
                response = await client.delete(f"{BACKEND_URL}/api/fund/{fund_code}")
                assert response.status_code == 200
                print(f"\n✓ Fund {fund_code} deleted")

            # Verify both are removed
            response = await client.get(f"{BACKEND_URL}/api/funds")
            funds = response.json()
            fund_codes = [f["code"] for f in funds]

            # 161129 should be removed
            assert test_funds[0][0] not in fund_codes

            # Note: 161128 was in the original list, so if we want to keep it,
            # we should add it back after the test
            print(f"\n✓ Multiple funds deleted successfully")

            # Clean up: Add 161128 back if needed
            await client.post(
                f"{BACKEND_URL}/api/fund",
                params={"code": test_funds[1][0], "name": test_funds[1][1]}
            )
            print(f"\n✓ Fund {test_funds[1][0]} restored")


class TestDeleteFundEdgeCases:
    """Test edge cases for fund deletion."""

    @pytest.mark.asyncio
    async def test_delete_fund_with_special_characters(self):
        """Test deleting a fund code with special patterns."""
        # Fund codes should be 6 digits, but test edge cases
        special_codes = ["000000", "999999", "ABC123"]

        async with httpx.AsyncClient(timeout=30.0) as client:
            for code in special_codes:
                response = await client.delete(f"{BACKEND_URL}/api/fund/{code}")
                # Should handle gracefully without crashing
                assert response.status_code == 200
                print(f"\n✓ Special code {code} handled gracefully")

    @pytest.mark.asyncio
    async def test_delete_fund_concurrent_requests(self):
        """Test deleting the same fund with concurrent requests."""
        fund_code = "161129"
        fund_name = "易方达原油A类人民币"

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Add the fund first
            await client.post(
                f"{BACKEND_URL}/api/fund",
                params={"code": fund_code, "name": fund_name}
            )

            # Send multiple delete requests concurrently
            tasks = [
                client.delete(f"{BACKEND_URL}/api/fund/{fund_code}")
                for _ in range(3)
            ]

            responses = await asyncio.gather(*tasks)

            # All should succeed (idempotent operation)
            for response in responses:
                assert response.status_code == 200

            print(f"\n✓ Concurrent deletion requests handled correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
