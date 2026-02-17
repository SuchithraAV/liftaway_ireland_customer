#!/bin/bash

# LiftAway Customer Backend - Secure Deployment Script
# This script ensures all security checks pass before deployment

set -e  # Exit on error

echo "🔍 LiftAway Customer Backend - Pre-Deployment Security Check"
echo "============================================================"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0
WARNINGS=0

# Check 1: Verify .env is in .gitignore
echo -e "\n📋 Check 1: Verifying .gitignore..."
if grep -q "^\.env$" .gitignore 2>/dev/null; then
    echo -e "${GREEN}✓${NC} .env is in .gitignore"
else
    echo -e "${RED}✗${NC} .env is NOT in .gitignore - CRITICAL"
    ERRORS=$((ERRORS + 1))
fi

# Check 2: Verify no hardcoded API keys in config.py
echo -e "\n🔑 Check 2: Checking for hardcoded API keys..."
if grep -q "sk-proj-" config.py 2>/dev/null; then
    echo -e "${RED}✗${NC} Hardcoded OpenAI API key found in config.py - CRITICAL"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}✓${NC} No hardcoded API keys in config.py"
fi

# Check 3: Verify environment variables are set
echo -e "\n🌍 Check 3: Verifying required environment variables..."
REQUIRED_VARS=(
    "OPENAI_API_KEY"
    "DATABASE_URL"
    "REDIS_URL"
    "SECRET_KEY"
    "STRIPE_SECRET_KEY"
)

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo -e "${RED}✗${NC} $var is not set"
        ERRORS=$((ERRORS + 1))
    else
        echo -e "${GREEN}✓${NC} $var is set"
    fi
done

# Check 4: Verify OpenAI API key format
echo -e "\n🤖 Check 4: Validating OpenAI API key..."
if [ -n "$OPENAI_API_KEY" ]; then
    if [[ $OPENAI_API_KEY == sk-* ]]; then
        echo -e "${GREEN}✓${NC} OpenAI API key format valid"
    else
        echo -e "${RED}✗${NC} Invalid OpenAI API key format"
        ERRORS=$((ERRORS + 1))
    fi
fi

# Check 5: Verify not using test Stripe keys in production
echo -e "\n💳 Check 5: Checking Stripe keys..."
if [ -n "$STRIPE_SECRET_KEY" ]; then
    if [[ $STRIPE_SECRET_KEY == sk_test_* ]]; then
        echo -e "${YELLOW}⚠${NC} Using Stripe TEST keys - WARNING"
        WARNINGS=$((WARNINGS + 1))
    elif [[ $STRIPE_SECRET_KEY == sk_live_* ]]; then
        echo -e "${GREEN}✓${NC} Using Stripe LIVE keys"
    fi
fi

# Check 6: Verify database is not dev database
echo -e "\n🗄️  Check 6: Checking database configuration..."
if [ -n "$DATABASE_URL" ]; then
    if [[ $DATABASE_URL == *"db_dev"* ]]; then
        echo -e "${YELLOW}⚠${NC} Using DEV database - WARNING"
        WARNINGS=$((WARNINGS + 1))
    else
        echo -e "${GREEN}✓${NC} Database configuration OK"
    fi
fi

# Check 7: Verify pricing slabs migration exists
echo -e "\n📊 Check 7: Checking pricing migration..."
if [ -f "alembic/versions/011_liftaway_pricing_update.py" ]; then
    echo -e "${GREEN}✓${NC} Pricing migration file exists"
else
    echo -e "${RED}✗${NC} Pricing migration file missing"
    ERRORS=$((ERRORS + 1))
fi

# Check 8: Verify seed file exists
echo -e "\n🌱 Check 8: Checking seed file..."
if [ -f "seed_liftaway_pricing.py" ]; then
    echo -e "${GREEN}✓${NC} Seed file exists"
else
    echo -e "${RED}✗${NC} Seed file missing"
    ERRORS=$((ERRORS + 1))
fi

# Summary
echo -e "\n============================================================"
echo -e "📊 Security Check Summary"
echo -e "============================================================"
echo -e "Errors: ${RED}$ERRORS${NC}"
echo -e "Warnings: ${YELLOW}$WARNINGS${NC}"

if [ $ERRORS -gt 0 ]; then
    echo -e "\n${RED}❌ DEPLOYMENT BLOCKED${NC}"
    echo -e "Fix all errors before deploying"
    exit 1
elif [ $WARNINGS -gt 0 ]; then
    echo -e "\n${YELLOW}⚠️  WARNINGS FOUND${NC}"
    echo -e "Review warnings before deploying"
    read -p "Continue with deployment? (yes/no): " -r
    if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
        echo "Deployment cancelled"
        exit 1
    fi
fi

echo -e "\n${GREEN}✅ All security checks passed${NC}"
echo -e "\n🚀 Proceeding with deployment..."

# Run migrations
echo -e "\n📦 Running database migrations..."
alembic upgrade head

# Seed pricing data
echo -e "\n🌱 Seeding pricing data..."
python seed_liftaway_pricing.py

# Build Docker image
echo -e "\n🐳 Building Docker image..."
docker build -t liftaway-customer-backend:latest .

echo -e "\n${GREEN}✅ Deployment preparation complete${NC}"
echo -e "\nNext steps:"
echo -e "1. docker run -d --name customer-backend -p 8000:8000 \\"
echo -e "   -e OPENAI_API_KEY=\"\$OPENAI_API_KEY\" \\"
echo -e "   -e DATABASE_URL=\"\$DATABASE_URL\" \\"
echo -e "   -e REDIS_URL=\"\$REDIS_URL\" \\"
echo -e "   -e SECRET_KEY=\"\$SECRET_KEY\" \\"
echo -e "   -e STRIPE_SECRET_KEY=\"\$STRIPE_SECRET_KEY\" \\"
echo -e "   liftaway-customer-backend:latest"
echo -e "\n2. curl http://localhost:8000/health/"
echo -e "3. Monitor logs: docker logs -f customer-backend"
