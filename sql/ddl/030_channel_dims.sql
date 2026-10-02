-- id: DDL030
-- name: Channel, campaign and acquisition-source dimensions
-- business_question: Attribute spend to campaigns/channels and users to the source that brought them.
-- tables: dim_channel, dim_campaign, dim_acquisition_source
-- grain: one row per channel / campaign / acquisition source
-- output: DDL only
-- kind: ddl
CREATE TABLE dim_channel (
    channel_key  INTEGER PRIMARY KEY,
    channel_name VARCHAR NOT NULL UNIQUE
);

CREATE TABLE dim_campaign (
    campaign_key  INTEGER PRIMARY KEY,
    campaign_name VARCHAR NOT NULL UNIQUE,
    channel_key   INTEGER NOT NULL REFERENCES dim_channel (channel_key)
);

CREATE TABLE dim_acquisition_source (
    source_key  INTEGER PRIMARY KEY,
    source_name VARCHAR NOT NULL UNIQUE,
    is_paid     BOOLEAN NOT NULL,
    channel_key INTEGER REFERENCES dim_channel (channel_key)   -- NULL for non-paid sources
);
