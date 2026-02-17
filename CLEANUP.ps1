# ============================================
# CLEANUP SCRIPT - Remove Unnecessary Files
# ============================================

Write-Host "Starting cleanup..." -ForegroundColor Yellow

# Delete duplicate SQL files
Remove-Item -Path "complete_database_setup.sql" -ErrorAction SilentlyContinue
Remove-Item -Path "create_17_tables.sql" -ErrorAction SilentlyContinue
Remove-Item -Path "create_tables.sql" -ErrorAction SilentlyContinue
Remove-Item -Path "add_refunded_at.sql" -ErrorAction SilentlyContinue

# Delete test/debug scripts
$testFiles = @(
    "check_db_state.py",
    "clear_customers.py",
    "create_tables.py",
    "debug_draft.py",
    "delete_all_customers.py",
    "delete_all_data.py",
    "diagnose.py",
    "encrypt_existing_data.py",
    "generate_sql.py",
    "increase_column_sizes.py",
    "reencrypt_customers.py",
    "test_db_connection_new.py",
    "test_db_connection.py",
    "test_draft_apis.py",
    "test_draft_flow.py",
    "test_old_decrypt.py",
    "test_production_pricing.py",
    "test_redis_detailed.py",
    "test_security_comprehensive.py",
    "truncate_customers.py",
    "verify_uk_pricing_compliance.py",
    "CRITICAL_SECURITY_FIXES.py"
)

foreach ($file in $testFiles) {
    Remove-Item -Path $file -ErrorAction SilentlyContinue
    Write-Host "Deleted: $file" -ForegroundColor Green
}

# Delete seed scripts
$seedFiles = @(
    "seed_categories.py",
    "seed_liftaway_pricing.py",
    "set_category_images.py",
    "update_category_images.py",
    "update_waste_categories.py"
)

foreach ($file in $seedFiles) {
    Remove-Item -Path $file -ErrorAction SilentlyContinue
    Write-Host "Deleted: $file" -ForegroundColor Green
}

# Delete log files
Remove-Item -Path "server.log" -ErrorAction SilentlyContinue

# Delete .qodo folder
Remove-Item -Path ".qodo" -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "Deleted: .qodo folder" -ForegroundColor Green

# Create docs folder and move documentation
New-Item -ItemType Directory -Path "docs" -Force | Out-Null

$docFiles = @(
    "AUTHENTICATION_FLOW_DIAGRAM.md",
    "BUSINESS_ANALYSIS.md",
    "DEPLOY_NOW.md",
    "DEPLOYMENT_CHECKLIST_PAYMENT_SECURITY.md",
    "DEPLOYMENT_SUCCESS.md",
    "DRAFT_API_FLOW_DIAGRAM.md",
    "DRAFT_API_GUIDE.md",
    "FIX_503_DRAFT_ERROR.md",
    "FIX_503_QUICK_SUMMARY.md",
    "INSUFFICIENT_BALANCE_FLOW.md",
    "LIVE_LOCATION_API.md",
    "LOCAL_TESTING_GUIDE.md",
    "PAY_FIRST_EXECUTIVE_SUMMARY.md",
    "PAY_FIRST_IMPLEMENTATION_COMPLETE.md",
    "PAY_FIRST_IMPLEMENTATION_PLAN.md",
    "PAYMENT_ARCHITECTURE_AUDIT.md",
    "PAYMENT_ERROR_HANDLING_AUDIT.md",
    "PAYMENT_ERROR_HANDLING_IMPLEMENTATION.md",
    "PAYMENT_ERROR_HANDLING_QUICK_REF.md",
    "PAYMENT_FLOW_ANALYSIS.md",
    "PRE_PRODUCTION_SUMMARY.md",
    "PRICING_ALGORITHM_ANALYSIS.md",
    "PRODUCTION_DEPLOYMENT_CHECKLIST.md",
    "PRODUCTION_READINESS_CHECK.md",
    "PRODUCTION_READINESS.md",
    "REDIS_FIX_PRODUCTION.md",
    "SECURITY_AUDIT_REPORT.md",
    "SECURITY_QUICK_SUMMARY.md",
    "START_HERE.md"
)

foreach ($file in $docFiles) {
    if (Test-Path $file) {
        Move-Item -Path $file -Destination "docs\" -Force -ErrorAction SilentlyContinue
        Write-Host "Moved to docs: $file" -ForegroundColor Cyan
    }
}

Write-Host "`nCleanup completed!" -ForegroundColor Green
Write-Host "Documentation moved to /docs folder" -ForegroundColor Cyan
Write-Host "`nEssential files kept:" -ForegroundColor Yellow
Write-Host "  - main.py, config.py, .env" -ForegroundColor White
Write-Host "  - core/ (application code)" -ForegroundColor White
Write-Host "  - FINAL_17_TABLES.sql (database schema)" -ForegroundColor White
Write-Host "  - README.md, Dockerfile, docker-compose.yml" -ForegroundColor White
