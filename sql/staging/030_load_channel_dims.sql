-- id: STG030
-- name: Load channel, campaign and acquisition-source dimensions
-- business_question: Key campaigns to channels and map paid acquisition sources to the channel that buys them.
-- tables: staging.stg_ref_channel, staging.stg_ref_campaign, staging.stg_ref_source, dim_channel, dim_campaign, dim_acquisition_source
-- grain: one row per channel / campaign / source
-- output: populated dim_channel, dim_campaign, dim_acquisition_source
-- kind: staging
INSERT INTO dim_channel (channel_key, channel_name)
SELECT row_number() OVER (ORDER BY channel_name), channel_name FROM staging.stg_ref_channel;

INSERT INTO dim_campaign (campaign_key, campaign_name, channel_key)
SELECT row_number() OVER (ORDER BY c.campaign_name), c.campaign_name, ch.channel_key
FROM staging.stg_ref_campaign c JOIN dim_channel ch ON ch.channel_name = c.channel_name;

INSERT INTO dim_acquisition_source (source_key, source_name, is_paid, channel_key)
SELECT row_number() OVER (ORDER BY s.source_name), s.source_name, s.is_paid, ch.channel_key
FROM staging.stg_ref_source s LEFT JOIN dim_channel ch ON ch.channel_name = s.channel_name;
