# Test Suite for QDII Fund Radar

This directory contains test cases for the QDII Fund Radar application.

## Running Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_purchase_limit_002732.py -v
python -m pytest tests/test_delete_fund_161129.py -v

# Run with detailed output
python -m pytest tests/test_delete_fund_161129.py -v -s

# Run specific test class
python -m pytest tests/test_delete_fund_161129.py::TestDeleteFund161129 -v

# Run specific test method
python -m pytest tests/test_delete_fund_161129.py::TestDeleteFund161129::test_delete_fund_161129_success -v
```

## Test Files

### test_purchase_limit_002732.py

Comprehensive test suite for purchase limit functionality, specifically focused on fund 002732.

**Test Coverage:**

1. **TestFormatLimitText** (10 tests)
   - Tests for the `format_limit_text()` function
   - Covers various limit statuses: suspended, limited, unlimited
   - Tests different limit formats: yuan (元), wan (万), yi (亿)
   - Edge cases: empty status, None status, very large limits

2. **TestExtractLimitValue** (6 tests)
   - Tests for the `extract_limit_value()` function
   - Extracts numeric limit values from formatted text
   - Handles various units: 万, 亿, 元
   - Tests suspended, unlimited, and empty states

3. **TestParseFundLimitFromHTML** (8 tests)
   - Tests for the `parse_fund_limit_from_html()` function
   - Parses HTML responses from fundf10.eastmoney.com
   - Handles various purchase statuses: 暂停申购, 开放申购, 限大额
   - Tests edge cases: empty HTML, None HTML, dash (---) status
   - Includes actual HTML from fund 002732

4. **TestFund002732Integration** (2 tests)
   - Integration test fetching actual data for fund 002732
   - Comprehensive coverage test with 15 different scenarios
   - Tests real API call to Eastmoney

5. **TestLimitValueExtractionEdgeCases** (3 tests)
   - Tests edge cases for limit value extraction
   - Handles decimals, whitespace, malformed strings

**Test Results:**
- Total: 29 tests
- Status: ✅ All passing

---

### test_delete_fund_161129.py

Comprehensive test suite for deleting funds from the fund list, specifically focused on fund 161129 (易方达原油A类人民币).

**Test Coverage:**

1. **TestAddFund161129** (2 tests)
   - Tests adding fund 161129 to the fund list via API
   - Verifies the fund appears in the list after adding

2. **TestDeleteFund161129** (3 tests)
   - Tests deleting fund 161129 via DELETE API endpoint
   - Verifies fund is removed from the funds list
   - Verifies fund is removed from funds.json file

3. **TestDeleteNonExistentFund** (2 tests)
   - Tests deleting a non-existent fund (999999)
   - Tests deleting the same fund twice (idempotent operation)

4. **TestDeleteFundDatabaseCleanup** (1 test)
   - Verifies monitoring status is removed when fund is deleted
   - Tests cleanup of monitored_funds database table

5. **TestDeleteFundIntegration** (2 tests)
   - Complete workflow test: add → verify → delete → verify
   - Tests deleting multiple funds in sequence

6. **TestDeleteFundEdgeCases** (2 tests)
   - Tests deleting funds with special/invalid codes
   - Tests concurrent deletion requests (race condition handling)

**Test Results:**
- Total: 12 tests
- Status: ✅ All passing

**Key Features:**
- Tests both API endpoints and file system changes
- Validates database cleanup
- Tests error handling for edge cases
- Includes integration tests for complete workflows

---

## Fund-Specific Tests

### Fund 002732 (易方达纳指100ETF联接美元A)
- Purchase status shows "---" (no specific data)
- Application defaults this to "开放" (open/unlimited)
- Limit text displayed as "不限" (no restriction)

### Fund 161129 (易方达原油A类人民币)
- Successfully tested add/delete workflow
- Verified database cleanup on deletion
- Tested concurrent deletion scenarios

## Test Dependencies

- **pytest**: Testing framework
- **pytest-asyncio**: Async test support
- **httpx**: HTTP client for API tests
- **boto3**: AWS SDK (for server.py imports)

## API Endpoints Tested

### Purchase Limit Tests
- `GET /api/funds` - Fetch all funds with limits
- `GET /api/funds?codes=002732` - Fetch specific fund
- HTML parsing from `https://fundf10.eastmoney.com/jjfl_{code}.html`

### Delete Fund Tests
- `POST /api/fund?code={code}&name={name}` - Add fund
- `DELETE /api/fund/{code}` - Delete fund
- `GET /api/funds` - List all funds
- `GET /api/notifications/monitored-funds/{code}` - Get monitoring status
- `PUT /api/notifications/monitored-funds/{code}` - Update monitoring status

## Backend Server

Tests require the backend server to be running:

```bash
# Start backend (port 8088)
source venv/bin/activate
python3 server.py
```

Or run in background:
```bash
source venv/bin/activate && python3 server.py &
```

## Test Best Practices

1. **Isolation**: Each test should be independent and not rely on other tests
2. **Cleanup**: Tests clean up after themselves (restore deleted funds)
3. **Async Support**: Tests use pytest-asyncio for async API calls
4. **Comprehensive**: Cover happy path, edge cases, and error handling
5. **Documentation**: Each test has clear docstrings explaining what it tests

## Adding New Tests

When adding new test files:

1. Name the test file: `test_<feature>_<fund_code>.py`
2. Use pytest conventions: test classes start with `Test`, test methods start with `test_`
3. Use `@pytest.mark.asyncio` for async tests
4. Group related tests in test classes
5. Add documentation to this README

Example test structure:
```python
class TestFeatureName:
    """Description of what this class tests."""

    @pytest.mark.asyncio
    async def test_specific_scenario(self):
        """Test description."""
        # Arrange
        # Act
        # Assert
        pass
```

## Troubleshooting

### Tests Fail with Connection Refused
- Ensure backend server is running on port 8088
- Check firewall settings

### Tests Fail with Module Not Found
- Ensure virtual environment is activated
- Install dependencies: `pip install pytest pytest-asyncio httpx boto3`

### Database Errors
- Check that `data/notifications.db` exists
- Verify database permissions
- Reinitialize database if needed

## Continuous Integration

To run tests in CI/CD:

```bash
# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-asyncio

# Run all tests with coverage
python -m pytest tests/ -v --cov=. --cov-report=html
```
