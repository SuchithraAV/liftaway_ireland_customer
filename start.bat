@echo off
set DATABASE_URL=
set REDIS_URL=
poetry run uvicorn main:app --reload --port 8000
