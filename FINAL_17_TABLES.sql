-- ============================================
-- DROP ALL TABLES (Including auto-created ones)
-- ============================================
DROP TABLE IF EXISTS job_transactions CASCADE;
DROP TABLE IF EXISTS platform_daily_revenue CASCADE;
DROP TABLE IF EXISTS driver_daily_earnings CASCADE;
DROP TABLE IF EXISTS waste_jobs CASCADE;
DROP TABLE IF EXISTS pricing_slabs CASCADE;
DROP TABLE IF EXISTS driver_wallet_transactions CASCADE;
DROP TABLE IF EXISTS driver_withdraw_requests CASCADE;
DROP TABLE IF EXISTS payments CASCADE;
DROP TABLE IF EXISTS schema_migrations CASCADE;
DROP TABLE IF EXISTS issue_ratings CASCADE;
DROP TABLE IF EXISTS issues CASCADE;
DROP TABLE IF EXISTS driver_vehicles CASCADE;
DROP TABLE IF EXISTS driver_vehicle_details CASCADE;
DROP TABLE IF EXISTS driver_professional_details CASCADE;
DROP TABLE IF EXISTS driver_personal_details CASCADE;
DROP TABLE IF EXISTS driver_locations CASCADE;
DROP TABLE IF EXISTS driver_earnings CASCADE;
DROP TABLE IF EXISTS driver_documents CASCADE;
DROP TABLE IF EXISTS driver_bank_details CASCADE;
DROP TABLE IF EXISTS notifications CASCADE;
DROP TABLE IF EXISTS chat_messages CASCADE;
DROP TABLE IF EXISTS drivers CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS companies CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS admins CASCADE;

-- ============================================
-- CREATE ONLY 17 CORE TABLES
-- ============================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE admins (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone_number VARCHAR(20) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    mobile_otp VARCHAR(6),
    otp_expires_at TIMESTAMPTZ,
    date_joined TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    image_url VARCHAR(500) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    address TEXT,
    contact_number VARCHAR(20),
    email VARCHAR(255),
    lat FLOAT,
    lng FLOAT,
    owner_id UUID REFERENCES admins(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    phone_number VARCHAR(20) NOT NULL,
    address TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    mobile_otp VARCHAR(6),
    otp_expires_at TIMESTAMPTZ,
    date_joined TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE drivers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE,
    password VARCHAR(255),
    full_name VARCHAR(255),
    phone_number VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    stripe_account_id VARCHAR(255),
    stripe_verification_status VARCHAR(50) DEFAULT 'pending',
    stripe_payouts_enabled BOOLEAN DEFAULT FALSE,
    stripe_requirements_due BOOLEAN DEFAULT FALSE,
    stripe_bank_last4 VARCHAR(4),
    is_approved VARCHAR(20) DEFAULT 'pending',
    is_online BOOLEAN DEFAULT FALSE,
    phone_otp VARCHAR(6),
    otp_expires_at TIMESTAMPTZ,
    date_joined TIMESTAMPTZ DEFAULT NOW(),
    is_phone_verified BOOLEAN DEFAULT FALSE,
    is_verified VARCHAR(20) DEFAULT 'pending',
    dob TIMESTAMP,
    address TEXT,
    years_experience INTEGER,
    previous_company VARCHAR(200),
    service_pincodes TEXT,
    preferred_shift VARCHAR(50),
    approval_status VARCHAR(20) DEFAULT 'pending'
);

CREATE TABLE driver_bank_details (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    driver_id UUID NOT NULL REFERENCES drivers(id) ON DELETE CASCADE,
    bank_account_number VARCHAR(100),
    bank_ifsc VARCHAR(20),
    account_holder_name VARCHAR(200),
    upi_id VARCHAR(100)
);

CREATE TABLE driver_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    driver_id UUID NOT NULL REFERENCES drivers(id) ON DELETE CASCADE,
    govt_id_type VARCHAR(50),
    govt_id_number VARCHAR(100),
    id_photo_url VARCHAR(500),
    selfie_photo_url VARCHAR(500),
    license_number VARCHAR(100),
    license_category VARCHAR(50),
    license_expiry_date TIMESTAMP,
    license_front_url VARCHAR(500),
    license_back_url VARCHAR(500),
    driver_photo_url VARCHAR(500)
);

CREATE TABLE driver_locations (
    id SERIAL PRIMARY KEY,
    driver_id UUID UNIQUE NOT NULL REFERENCES drivers(id),
    lat FLOAT NOT NULL,
    lng FLOAT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE driver_personal_details (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    driver_id UUID UNIQUE NOT NULL REFERENCES drivers(id) ON DELETE CASCADE,
    dob DATE,
    address TEXT,
    years_experience INTEGER,
    previous_company VARCHAR(200),
    service_pincodes TEXT,
    preferred_shift VARCHAR(50)
);

CREATE TABLE driver_professional_details (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    driver_id UUID UNIQUE NOT NULL REFERENCES drivers(id) ON DELETE CASCADE,
    years_experience INTEGER,
    previous_company VARCHAR(200),
    service_pincodes TEXT,
    preferred_shift VARCHAR(50),
    specializations TEXT
);

CREATE TABLE driver_vehicle_details (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    driver_id UUID UNIQUE NOT NULL REFERENCES drivers(id) ON DELETE CASCADE,
    vehicle_type VARCHAR(50),
    vehicle_number_plate VARCHAR(50),
    vehicle_model VARCHAR(100),
    vehicle_capacity VARCHAR(50),
    vehicle_photo_url VARCHAR(500),
    rc_book_pic_url VARCHAR(500),
    pollution_cert_pic_url VARCHAR(500)
);

CREATE TABLE driver_vehicles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    driver_id UUID NOT NULL REFERENCES drivers(id) ON DELETE CASCADE,
    vehicle_type VARCHAR(50),
    vehicle_number_plate VARCHAR(50),
    vehicle_model VARCHAR(100),
    vehicle_capacity VARCHAR(50),
    vehicle_photo_url VARCHAR(500),
    rc_book_pic_url VARCHAR(500),
    pollution_cert_pic_url VARCHAR(500)
);

CREATE TABLE issues (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id UUID NOT NULL REFERENCES customers(id),
    category_id INTEGER NOT NULL REFERENCES categories(id),
    description TEXT NOT NULL,
    pickup_location VARCHAR(500) NOT NULL,
    images JSON NOT NULL,
    assigned_driver_id UUID REFERENCES drivers(id),
    driver_location VARCHAR(100),
    status VARCHAR(20) DEFAULT 'awaiting_payment' NOT NULL,
    otp_code VARCHAR(6) NOT NULL,
    payment_amount DECIMAL(10, 2) NOT NULL,
    negotiated_price DECIMAL(10, 2),
    negotiated_status VARCHAR(20) DEFAULT 'pending',
    payment_status VARCHAR(10) DEFAULT 'unpaid' NOT NULL,
    stripe_payment_intent_id VARCHAR(255),
    paid_at TIMESTAMPTZ,
    refunded_at TIMESTAMPTZ,
    scheduled_date DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE driver_earnings (
    id SERIAL PRIMARY KEY,
    driver_id UUID NOT NULL REFERENCES drivers(id),
    issue_id UUID NOT NULL REFERENCES issues(id),
    date TIMESTAMPTZ NOT NULL,
    jobs_done INTEGER DEFAULT 1,
    amount DECIMAL(10, 2) NOT NULL,
    total_job_amount DECIMAL(10, 2),
    platform_fee DECIMAL(10, 2),
    stripe_transfer_id VARCHAR(255),
    payout_status VARCHAR(20) DEFAULT 'pending' NOT NULL,
    available_for_payout BOOLEAN DEFAULT FALSE,
    paid_at TIMESTAMPTZ
);

CREATE TABLE issue_ratings (
    id SERIAL PRIMARY KEY,
    issue_id UUID NOT NULL REFERENCES issues(id),
    customer_id UUID NOT NULL REFERENCES customers(id),
    driver_id UUID NOT NULL REFERENCES drivers(id),
    rating INTEGER NOT NULL,
    comments TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    issue_id UUID NOT NULL REFERENCES issues(id),
    sender_id UUID NOT NULL,
    sender_type VARCHAR(20) NOT NULL,
    encrypted_text TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    user_type VARCHAR(20) NOT NULL,
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    data JSON,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

SELECT 'Exactly 17 tables created!' AS status;
