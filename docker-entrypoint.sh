#!/bin/bash
set -e

echo "🚀 Starting LiftAway Customer Backend..."

# Run database migrations
echo "📦 Running database migrations..."
alembic upgrade head

# Seed pricing data (idempotent - won't duplicate if already exists)
echo "🌱 Seeding pricing data..."
python seed_liftaway_pricing.py || echo "⚠️  Pricing data already seeded or seed failed"

echo "✅ Initialization complete. Starting application..."

# Execute the main command
exec "$@"
