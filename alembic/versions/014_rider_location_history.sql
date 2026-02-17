"""
PostgreSQL Schema for Historical Location Logging
Optional: Store location history for analytics and debugging
"""

-- Rider Location History Table
CREATE TABLE IF NOT EXISTS rider_location_history (
    id SERIAL PRIMARY KEY,
    rider_id UUID NOT NULL,
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(11, 8) NOT NULL,
    heading DECIMAL(5, 2),  -- Direction in degrees (0-360)
    speed DECIMAL(6, 2),  -- Speed in km/h
    accuracy DECIMAL(8, 2),  -- GPS accuracy in meters
    geojson JSONB,  -- GeoJSON Point for PostGIS queries
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Indexes for performance
    INDEX idx_rider_location_rider_id (rider_id),
    INDEX idx_rider_location_created_at (created_at),
    INDEX idx_rider_location_rider_time (rider_id, created_at DESC)
);

-- Enable PostGIS extension for geospatial queries (optional)
-- CREATE EXTENSION IF NOT EXISTS postgis;

-- Add spatial index if using PostGIS
-- CREATE INDEX idx_rider_location_geom ON rider_location_history USING GIST ((geojson::geometry));

-- Partition by month for better performance (optional)
-- CREATE TABLE rider_location_history_2025_01 PARTITION OF rider_location_history
-- FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

-- Function to automatically log location updates (optional trigger)
CREATE OR REPLACE FUNCTION log_rider_location()
RETURNS TRIGGER AS $$
BEGIN
    -- Auto-cleanup old records (keep last 30 days)
    DELETE FROM rider_location_history 
    WHERE created_at < NOW() - INTERVAL '30 days';
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-cleanup on insert
CREATE TRIGGER trigger_cleanup_old_locations
AFTER INSERT ON rider_location_history
FOR EACH STATEMENT
EXECUTE FUNCTION log_rider_location();

-- Query examples:

-- Get rider's location history for last 24 hours
-- SELECT * FROM rider_location_history 
-- WHERE rider_id = 'xxx' 
-- AND created_at > NOW() - INTERVAL '24 hours'
-- ORDER BY created_at DESC;

-- Get rider's route (ordered points)
-- SELECT latitude, longitude, created_at 
-- FROM rider_location_history 
-- WHERE rider_id = 'xxx' 
-- AND created_at BETWEEN '2025-01-01' AND '2025-01-02'
-- ORDER BY created_at ASC;

-- Calculate distance traveled (requires PostGIS)
-- SELECT 
--     rider_id,
--     SUM(ST_Distance(
--         ST_Transform(ST_SetSRID(ST_MakePoint(longitude, latitude), 4326), 3857),
--         ST_Transform(ST_SetSRID(ST_MakePoint(
--             LAG(longitude) OVER (ORDER BY created_at),
--             LAG(latitude) OVER (ORDER BY created_at)
--         ), 4326), 3857)
--     )) / 1000 as distance_km
-- FROM rider_location_history
-- WHERE rider_id = 'xxx'
-- GROUP BY rider_id;
