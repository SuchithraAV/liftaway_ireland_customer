-- Add Stripe fields to existing tables
ALTER TABLE issues ADD COLUMN stripe_payment_intent_id VARCHAR(255) NULL AFTER payment_status;

ALTER TABLE drivers ADD COLUMN stripe_account_id VARCHAR(255) NULL AFTER is_active;

ALTER TABLE driver_earnings ADD COLUMN stripe_transfer_id VARCHAR(255) NULL AFTER amount;
ALTER TABLE driver_earnings ADD COLUMN payout_status VARCHAR(20) NOT NULL DEFAULT 'pending' AFTER stripe_transfer_id;

-- Create issue_ratings table
CREATE TABLE IF NOT EXISTS issue_ratings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    issue_id CHAR(36) NOT NULL,
    customer_id CHAR(36) NOT NULL,
    driver_id CHAR(36) NOT NULL,
    rating INT NOT NULL,
    comments TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
    FOREIGN KEY (driver_id) REFERENCES drivers(id) ON DELETE CASCADE,
    UNIQUE KEY unique_issue_rating (issue_id)
);

-- Add indexes for better query performance
CREATE INDEX idx_issue_ratings_driver ON issue_ratings(driver_id);
CREATE INDEX idx_issue_ratings_customer ON issue_ratings(customer_id);
CREATE INDEX idx_driver_earnings_payout_status ON driver_earnings(payout_status);
