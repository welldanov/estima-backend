-- CITIES

CREATE TABLE IF NOT EXISTS cities (
    id INTEGER PRIMARY KEY NOT NULL,
    name TEXT NOT NULL
) STRICT;


-- LISTINGS

CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY NOT NULL,
    city_id INTEGER NOT NULL REFERENCES cities(id),
    property_type  TEXT NOT NULL CHECK (property_type IN ('apartment', 'house', 'land')),

    title TEXT NOT NULL,
    description TEXT NOT NULL,
    price INTEGER NOT NULL CHECK (price > 0),

    address TEXT NOT NULL,
    district TEXT,

    lat REAL NOT NULL CHECK (lat BETWEEN -90 AND 90),
    lon REAL NOT NULL CHECK (lon BETWEEN -180 AND 180),

    url TEXT NOT NULL,

    first_seen_at  TEXT NOT NULL,
    last_seen_at   TEXT NOT NULL,
    CHECK (first_seen_at <= last_seen_at)
) STRICT;


-- APARTMENTS

CREATE TABLE IF NOT EXISTS apartments (
    listing_id   INTEGER PRIMARY KEY REFERENCES listings(id) ON DELETE CASCADE,
    area_m2      REAL NOT NULL CHECK (area_m2 > 0),
    rooms        INTEGER CHECK (rooms IS NULL OR rooms > 0),
    is_studio    INTEGER NOT NULL CHECK (is_studio IN (0, 1)),
    floor        INTEGER NOT NULL CHECK (floor > 0),
    floors_total INTEGER NOT NULL CHECK (floors_total > 0),
    CHECK (floor <= floors_total),
    CHECK ((is_studio = 1) = (rooms IS NULL))
) STRICT;


-- HOUSES

CREATE TABLE IF NOT EXISTS houses (
    listing_id    INTEGER PRIMARY KEY REFERENCES listings(id) ON DELETE CASCADE,
    house_kind    TEXT NOT NULL CHECK (house_kind IN ('house', 'dacha', 'cottage', 'townhouse')),
    house_area_m2 REAL NOT NULL CHECK (house_area_m2 > 0),
    land_area_m2  REAL NOT NULL CHECK (land_area_m2 > 0)
) STRICT;


-- LANDS

CREATE TABLE IF NOT EXISTS lands (
    listing_id   INTEGER PRIMARY KEY REFERENCES listings(id) ON DELETE CASCADE,
    land_area_m2 REAL NOT NULL CHECK (land_area_m2 > 0),
    land_type    TEXT NOT NULL CHECK (land_type IN ('izhs', 'snt_dnp', 'lph', 'industrial'))
) STRICT;


-- ============================================================

-- INDEXES

CREATE INDEX IF NOT EXISTS idx_listings_city_type
    ON listings(city_id, property_type);