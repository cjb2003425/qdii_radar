"""
Test cases for fund deletion functionality.
Tests that deleting a fund from the web UI properly removes it from funds.json
"""
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import tempfile
import os
import sys

# Add parent directory to path to import server
sys.path.insert(0, str(Path(__file__).parent.parent))

from server import app, get_db
from notifications.models import Base, MonitoredFund


class TestFundDeletion:
    """Test fund deletion endpoint and side effects."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)

    @pytest.fixture
    def test_funds_file(self):
        """Create a temporary funds.json file for testing."""
        test_data = {
            "funds": [
                {"code": "513100", "name": "国泰纳斯达克100ETF(QDII)"},
                {"code": "161130", "name": "易方达纳指100ETF联接A"},
                {"code": "021870", "name": "嘉实上证科创板芯片ETF发起联接I"}
            ],
            "config": {
                "api": {
                    "backendUrl": "http://127.0.0.1:8000/api/funds",
                    "requestTimeout": 20000,
                    "userAgent": "Test"
                }
            }
        }

        # Create temp file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(test_data, f, ensure_ascii=False, indent=2)
            temp_path = f.name

        yield temp_path

        # Cleanup
        os.unlink(temp_path)

    @pytest.fixture
    def test_db(self):
        """Create a temporary database for testing."""
        # Use in-memory SQLite database
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        TestingSessionLocal = sessionmaker(bind=engine)

        # Add test data
        session = TestingSessionLocal()
        session.add(MonitoredFund(fund_code="513100", enabled=True))
        session.add(MonitoredFund(fund_code="161130", enabled=True))
        session.add(MonitoredFund(fund_code="021870", enabled=True))
        session.commit()

        yield engine, TestingSessionLocal

        session.close()
        engine.dispose()

    def test_delete_fund_removes_from_funds_json(self, client, test_funds_file, monkeypatch):
        """Test that deleting a fund removes it from funds.json file."""
        # Patch the funds file path to use our test file
        def mock_get_funds_path():
            return Path(test_funds_file)

        monkeypatch.setattr("server.Path", lambda *args, **kwargs: mock_get_funds_path() if "funds.json" in str(args) else Path(*args, **kwargs))

        # Verify fund exists before deletion
        with open(test_funds_file, 'r', encoding='utf-8') as f:
            data_before = json.load(f)

        fund_codes_before = [f["code"] for f in data_before["funds"]]
        assert "021870" in fund_codes_before
        assert len(fund_codes_before) == 3

        # Delete the fund
        response = client.delete("/api/fund/021870")

        # Verify API response
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "删除成功" in result["message"]

        # Verify fund was removed from funds.json
        with open(test_funds_file, 'r', encoding='utf-8') as f:
            data_after = json.load(f)

        fund_codes_after = [f["code"] for f in data_after["funds"]]
        assert "021870" not in fund_codes_after
        assert len(fund_codes_after) == 2
        assert "513100" in fund_codes_after
        assert "161130" in fund_codes_after

    def test_delete_nonexistent_fund(self, client, test_funds_file, monkeypatch):
        """Test that deleting a non-existent fund returns appropriate error."""
        # Patch the funds file path
        def mock_get_funds_path():
            return Path(test_funds_file)

        monkeypatch.setattr("server.Path", lambda *args, **kwargs: mock_get_funds_path() if "funds.json" in str(args) else Path(*args, **kwargs))

        # Try to delete a fund that doesn't exist
        response = client.delete("/api/fund/999999")

        # Verify error response
        assert response.status_code == 200  # API returns 200 even for non-existent
        result = response.json()
        assert result["success"] is False
        assert "不存在" in result["message"]

    def test_delete_fund_from_monitored_funds(self, client, test_funds_file, test_db, monkeypatch):
        """Test that deleting a fund also removes it from monitoring database."""
        engine, TestingSessionLocal = test_db

        # Patch the funds file path
        def mock_get_funds_path():
            return Path(test_funds_file)

        monkeypatch.setattr("server.Path", lambda *args, **kwargs: mock_get_funds_path() if "funds.json" in str(args) else Path(*args, **kwargs))

        # Patch get_db to use our test database
        def override_get_db():
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                pass

        # Verify fund exists in database before deletion
        session = TestingSessionLocal()
        monitored_before = session.query(MonitoredFund).filter_by(fund_code="021870").first()
        assert monitored_before is not None
        session.close()

        # Delete the fund
        response = client.delete("/api/fund/021870")
        assert response.status_code == 200

        # Verify fund was removed from monitoring database
        session = TestingSessionLocal()
        monitored_after = session.query(MonitoredFund).filter_by(fund_code="021870").first()
        assert monitored_after is None
        session.close()

        # Verify other funds are still in database
        session = TestingSessionLocal()
        remaining_funds = session.query(MonitoredFund).all()
        fund_codes = [f.fund_code for f in remaining_funds]
        assert "513100" in fund_codes
        assert "161130" in fund_codes
        assert len(fund_codes) == 2
        session.close()

    def test_delete_multiple_funds(self, client, test_funds_file, monkeypatch):
        """Test deleting multiple funds sequentially."""
        # Patch the funds file path
        def mock_get_funds_path():
            return Path(test_funds_file)

        monkeypatch.setattr("server.Path", lambda *args, **kwargs: mock_get_funds_path() if "funds.json" in str(args) else Path(*args, **kwargs))

        # Delete first fund
        response1 = client.delete("/api/fund/021870")
        assert response1.status_code == 200
        assert response1.json()["success"] is True

        # Verify first deletion
        with open(test_funds_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert len(data["funds"]) == 2

        # Delete second fund
        response2 = client.delete("/api/fund/161130")
        assert response2.status_code == 200
        assert response2.json()["success"] is True

        # Verify second deletion
        with open(test_funds_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert len(data["funds"]) == 1
        assert data["funds"][0]["code"] == "513100"

    def test_funds_json_integrity_after_deletion(self, client, test_funds_file, monkeypatch):
        """Test that funds.json maintains valid JSON structure after deletion."""
        # Patch the funds file path
        def mock_get_funds_path():
            return Path(test_funds_file)

        monkeypatch.setattr("server.Path", lambda *args, **kwargs: mock_get_funds_path() if "funds.json" in str(args) else Path(*args, **kwargs))

        # Delete fund
        client.delete("/api/fund/021870")

        # Verify file is still valid JSON
        try:
            with open(test_funds_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Verify structure
            assert "funds" in data
            assert "config" in data
            assert isinstance(data["funds"], list)
            assert len(data["funds"]) == 2

            # Verify config section is intact
            assert "api" in data["config"]
            assert data["config"]["api"]["requestTimeout"] == 20000

        except json.JSONDecodeError:
            pytest.fail("funds.json is not valid JSON after deletion")


def run_integration_test():
    """
    Simple integration test that can be run manually.
    Tests the actual DELETE endpoint with a temporary file.
    """
    import httpx

    print("\n=== Integration Test: Delete Fund ===\n")

    # Create a temporary funds.json
    temp_file = Path("/tmp/test_funds.json")
    test_data = {
        "funds": [
            {"code": "513100", "name": "Test ETF"},
            {"code": "999999", "name": "Test Fund to Delete"}
        ],
        "config": {
            "api": {
                "backendUrl": "http://127.0.0.1:8000/api/funds",
                "requestTimeout": 20000,
                "userAgent": "Test"
            }
        }
    }

    # Backup original funds.json
    original_funds = Path(__file__).parent.parent / "data" / "funds.json"
    backup_file = Path(__file__).parent.parent / "data" / "funds.json.backup"

    try:
        # Create backup
        print(f"Backing up {original_funds} to {backup_file}")
        import shutil
        shutil.copy(original_funds, backup_file)

        # Copy test file
        print(f"Creating test funds.json with fund 999999")
        shutil.copy(temp_file, original_funds)

        # Test the endpoint
        print("\n1. Testing DELETE /api/fund/999999")
        response = httpx.delete("http://127.0.0.1:8000/api/fund/999999", timeout=10.0)

        if response.status_code == 200:
            result = response.json()
            print(f"   Response: {result}")
            assert result["success"] is True, "Delete request failed"
            print("   ✓ Fund deleted successfully via API")
        else:
            print(f"   ✗ Request failed with status {response.status_code}")
            return False

        # Verify deletion in file
        print("\n2. Verifying deletion in funds.json")
        with open(original_funds, 'r', encoding='utf-8') as f:
            data = json.load(f)

        fund_codes = [f["code"] for f in data["funds"]]
        if "999999" not in fund_codes:
            print("   ✓ Fund 999999 successfully removed from funds.json")
        else:
            print("   ✗ Fund 999999 still in funds.json")
            return False

        print("\n✓ All integration tests passed!\n")

    except Exception as e:
        print(f"\n✗ Test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Restore original
        print(f"\nRestoring original funds.json from backup")
        shutil.copy(backup_file, original_funds)
        backup_file.unlink()
        temp_file.unlink()

    return True


if __name__ == "__main__":
    """
    Run the integration test manually.
    Requires the backend server to be running.
    """
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║         Fund Deletion Integration Test                   ║
    ╚══════════════════════════════════════════════════════════╝

    This test will:
    1. Backup your current funds.json
    2. Create a test fund (999999) in funds.json
    3. Call DELETE /api/fund/999999
    4. Verify the fund is removed from funds.json
    5. Restore your original funds.json

    Make sure the backend server is running:
    $ python3 server.py

    Press Enter to continue or Ctrl+C to cancel...
    """)

    input()

    success = run_integration_test()

    if success:
        print("✓ Test completed successfully!")
        sys.exit(0)
    else:
        print("✗ Test failed!")
        sys.exit(1)
