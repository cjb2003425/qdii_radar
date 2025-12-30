# Fund Deletion Tests

Tests for verifying that the fund deletion functionality properly removes funds from both the frontend UI and the backend `funds.json` file.

## Problem Statement

When a user deletes a fund from the web UI, it should be removed from:
1. ✅ Frontend localStorage (always works)
2. ❌ Backend `funds.json` (requires backend server to be running)

If the backend server is not running, the DELETE API call fails silently, and the fund remains in `funds.json`. When the page reloads, the fund reappears.

## Test Files

### `test_delete_fund.py`

Comprehensive test suite for fund deletion functionality.

**Test Cases:**
1. ✅ `test_delete_fund_removes_from_funds_json` - Verifies fund is removed from funds.json
2. ✅ `test_delete_nonexistent_fund` - Tests error handling for non-existent funds
3. ✅ `test_delete_fund_from_monitored_funds` - Verifies removal from monitoring database
4. ✅ `test_delete_multiple_funds` - Tests sequential deletions
5. ✅ `test_funds_json_integrity_after_deletion` - Ensures JSON structure remains valid

## Running Tests

### Option 1: Run with pytest (Unit Tests)

```bash
# Install pytest if not already installed
pip install pytest httpx

# Run all tests
pytest tests/test_delete_fund.py -v

# Run specific test
pytest tests/test_delete_fund.py::TestFundDeletion::test_delete_fund_removes_from_funds_json -v
```

### Option 2: Run Integration Test Manually

The integration test requires the backend server to be running:

```bash
# Terminal 1: Start the backend server
python3 server.py

# Terminal 2: Run the integration test
cd tests
python test_delete_fund.py
```

The integration test will:
1. Backup your current `funds.json`
2. Add a test fund (999999) to `funds.json`
3. Call `DELETE /api/fund/999999`
4. Verify the fund is removed from `funds.json`
5. Restore your original `funds.json`

## Expected Behavior

### When Backend Server is Running ✅

```javascript
// User clicks "Delete" in FundManager UI
handleRemoveFund("021870", false)
  ↓
// 1. Remove from localStorage
removeUserFund("021870")  // ✅ Always works
  ↓
// 2. Call backend API
DELETE http://127.0.0.1:8000/api/fund/021870  // ✅ Success
  ↓
// Backend actions:
- Remove from funds.json
- Remove from monitoring database
- Reload QDII_FUNDS
  ↓
// 3. Refresh UI
onFundRemoved("021870")
  ↓
Result: Fund permanently deleted from everywhere ✅
```

### When Backend Server is NOT Running ❌

```javascript
// User clicks "Delete" in FundManager UI
handleRemoveFund("021870", false)
  ↓
// 1. Remove from localStorage
removeUserFund("021870")  // ✅ Works
  ↓
// 2. Call backend API
DELETE http://127.0.0.1:8000/api/fund/021870  // ❌ Connection refused
  ↓
// Error logged but not shown to user
console.warn('Failed to call backend delete fund API')
  ↓
// 3. Refresh UI (fund appears to be deleted)
onFundRemoved("021870")
  ↓
// 4. Page reload
User refreshes the page
  ↓
Fund reappears because it's still in funds.json ❌
```

## Solution

**Always ensure the backend server is running before deleting funds:**

```bash
# Check if backend is running
curl http://127.0.0.1:8000/health

# If not running, start it
python3 server.py
```

Or improve the frontend to show an error when backend deletion fails:

```typescript
// In FundManager.tsx
if (!deleteResponse.ok) {
  setError('无法从服务器删除基金，请确保后端服务正在运行');
  return;
}
```

## Test Coverage

| Test Case | Purpose | Status |
|-----------|---------|--------|
| Remove from funds.json | Verify backend deletion | ✅ |
| Non-existent fund | Error handling | ✅ |
| Remove from monitoring DB | Database cleanup | ✅ |
| Multiple deletions | Sequential operations | ✅ |
| JSON integrity | File structure validation | ✅ |

## Troubleshooting

### Backend server not running

**Symptom:** Tests fail with connection errors

**Solution:**
```bash
python3 server.py
```

### Port 8000 already in use

**Symptom:** Backend won't start

**Solution:**
```bash
# Kill existing process
lsof -ti:8000 | xargs kill -9

# Restart backend
python3 server.py
```

### Tests pass but fund still appears

**Symptom:** Integration test passes but fund reappears on reload

**Possible Causes:**
1. Browser cache - clear cache and reload
2. Multiple fund entries - check for duplicates in funds.json
3. localStorage not cleared - clear browser localStorage

## Files Modified

- `tests/test_delete_fund.py` - Test suite
- `server.py:827-875` - DELETE endpoint (already implemented)
- `components/FundManager.tsx:121-142` - Frontend delete handler (already implemented)

## Next Steps

To improve the user experience:

1. ✅ Add error message when backend deletion fails
2. ✅ Show loading state during deletion
3. ⏳ Add retry mechanism for failed deletions
4. ⏳ Show backend server status in UI
5. ⏳ Auto-retry deletion on server reconnect
