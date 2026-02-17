-- Migration: Add awaiting_payment status to issues table
-- Date: 2024-01-XX
-- Description: Adds new 'awaiting_payment' status for pay-first flow

-- This migration is safe to run on existing data
-- Existing issues with status='pending' will remain as 'pending' (already paid)
-- New issues will be created with status='awaiting_payment' until payment is completed

-- No changes needed to the database schema
-- The status column already supports string values up to 20 characters
-- The new status 'awaiting_payment' (17 chars) fits within the existing VARCHAR(20) column

-- Optional: If you want to verify the column definition
-- SELECT column_name, data_type, character_maximum_length 
-- FROM information_schema.columns 
-- WHERE table_name = 'issues' AND column_name = 'status';

-- No SQL changes required - this is a code-level change only
-- The application will handle the new status value
