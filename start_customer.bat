@echo off
echo Starting Breakdown Assistance Customer Backend...
echo Port: 8000
echo Docs: http://localhost:8000/docs
uvicorn main:app --reload --host 0.0.0.0 --port 8000
pause