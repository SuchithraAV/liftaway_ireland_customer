@echo off
echo ============================================================
echo DRAFT API LOCAL TESTING
echo ============================================================
echo.

REM Check if server is running
echo [1/5] Checking if server is running...
curl -s http://localhost:8000/health/ >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Server is not running!
    echo.
    echo Please start the server first:
    echo   uvicorn main:app --reload --host 0.0.0.0 --port 8000
    echo.
    pause
    exit /b 1
)
echo OK - Server is running
echo.

REM Test 1: Health Check
echo [2/5] Testing Health Check...
curl -s http://localhost:8000/health/
echo.
echo.

REM Test 2: Draft Creation
echo [3/5] Testing Draft Creation (No Auth)...
curl -s -X POST http://localhost:8000/api/v1/customer/issue/draft ^
  -F "category_id=1" ^
  -F "description=Test waste collection from automated test" ^
  -F "pickup_location=123 Test Street, London" ^
  -F "quantity=3" ^
  -F "urgency=urgent" ^
  -F "vehicle_size=small_van" ^
  -F "postcode=SW1A 1AA"
echo.
echo.

REM Test 3: Rate Limiting
echo [4/5] Testing Rate Limiting (sending 15 requests)...
echo This should show 429 error after 10 requests
echo.
set count=0
for /L %%i in (1,1,15) do (
  set /a count+=1
  curl -s -o nul -w "Request %%i: HTTP %%{http_code}\n" ^
    -X POST http://localhost:8000/api/v1/customer/issue/draft ^
    -F "category_id=1" ^
    -F "description=Rate limit test" ^
    -F "pickup_location=London"
)
echo.
echo.

REM Test 4: API Documentation
echo [5/5] Checking API Documentation...
echo Opening browser to view API docs...
start http://localhost:8000/docs
echo.

REM Summary
echo ============================================================
echo TEST SUMMARY
echo ============================================================
echo.
echo Expected Results:
echo   [1] Health check: status=healthy, redis=connected
echo   [2] Draft creation: 201 Created with draft_id and price
echo   [3] Rate limiting: HTTP 429 after request 10
echo   [4] API docs: Should open in browser
echo.
echo If all tests passed, your Draft APIs are working correctly!
echo.
echo Next Steps:
echo   1. Test with authentication (see LOCAL_TESTING_GUIDE.md)
echo   2. Test draft fetch and confirm endpoints
echo   3. Review PRODUCTION_DEPLOYMENT_CHECKLIST.md
echo.
echo ============================================================
pause
