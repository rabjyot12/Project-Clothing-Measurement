-- New table; does not modify existing garments data.
CREATE TABLE IF NOT EXISTS garment_measurements_v2 (
 id UUID PRIMARY KEY, garment_name TEXT NOT NULL, garment_type TEXT NOT NULL,
 image_filename TEXT, image_width INTEGER NOT NULL, image_height INTEGER NOT NULL,
 reference_cm DOUBLE PRECISION NOT NULL, calibration_pixels DOUBLE PRECISION NOT NULL,
 measurements_cm JSONB NOT NULL, manual_truth_cm JSONB, validation_report JSONB,
 point_data JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
