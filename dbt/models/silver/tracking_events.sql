-- Silver tracking_events: dedup, conform carrier-specific codes into a canonical
-- event_name, and normalize every timestamp variant to UTC.
-- Ported from notebooks/silver_layer.py (Step 2).

with deduped as (
    select
        *,
        row_number() over (partition by event_id order by event_received_at desc) as rn
    from {{ source('raw', 'tracking_events') }}
),

normalized as (
    -- Rewrite each carrier/corrupted event_at string into an explicit-offset
    -- ISO-8601 string so a single parse yields the correct UTC instant.
    select
        event_id,
        label_id,
        carrier,
        event_code,
        event_type,
        event_at as event_at_raw,
        event_received_at,
        location_zip,
        raw_payload,
        regexp_extract(event_at, ' ([A-Z]{2,4})$', 1) as tz_abbr,
        case
            -- 1) Timezone abbreviation (DHL) -> swap abbr for its numeric offset
            when regexp_extract(event_at, ' ([A-Z]{2,4})$', 1) <> '' then
                regexp_replace(event_at, ' [A-Z]{2,4}$', '') ||
                case regexp_extract(event_at, ' ([A-Z]{2,4})$', 1)
                    when 'EST' then '-05:00' when 'EDT' then '-04:00'
                    when 'CST' then '-06:00' when 'CDT' then '-05:00'
                    when 'MST' then '-07:00' when 'MDT' then '-06:00'
                    when 'PST' then '-08:00' when 'PDT' then '-07:00'
                    else 'Z'
                end
            -- 2) Already carries an explicit offset or Z (USPS, UPS) -> keep
            when event_at rlike 'T[0-9]{2}:[0-9]{2}:[0-9]{2}([+-][0-9]{2}:[0-9]{2}|Z)$' then event_at
            -- 3) Corrupted: no separators -> rebuild + assume UTC (tz destroyed)
            when event_at rlike '^[0-9]{8}T[0-9]{6}$' then
                substr(event_at, 1, 4) || '-' || substr(event_at, 5, 2) || '-' || substr(event_at, 7, 2) || 'T' ||
                substr(event_at, 10, 2) || ':' || substr(event_at, 12, 2) || ':' || substr(event_at, 14, 2) || 'Z'
            -- 4) Corrupted: wrong separators (slashes) -> dashes + assume UTC
            when event_at rlike '^[0-9]{4}/[0-9]{2}/[0-9]{2}' then replace(event_at, '/', '-') || 'Z'
            -- 5) Corrupted: date only -> midnight UTC
            when event_at rlike '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then event_at || 'T00:00:00Z'
            -- 6) Plain ISO, no tz (FEDEX) -> assume UTC
            when event_at rlike '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}$' then event_at || 'Z'
            else event_at
        end as normalized_iso
    from deduped
    where rn = 1
),

parsed_events as (
    select
        event_id,
        label_id,
        carrier,
        event_code,
        event_type,
        -- Conform carrier-specific codes/types into a canonical event_name
        case coalesce(event_code, event_type)
            when '0300' then 'picked_up'
            when 'PICKUP' then 'picked_up'
            when 'PU' then 'picked_up'
            when '0301' then 'in_transit'
            when 'IN_TRANSIT' then 'in_transit'
            when 'IT' then 'in_transit'
            when '0310' then 'out_for_delivery'
            when 'OUT_FOR_DELIVERY' then 'out_for_delivery'
            when 'OFD' then 'out_for_delivery'
            when '0320' then 'delivered'
            when 'DELIVERED' then 'delivered'
            when 'DL' then 'delivered'
            else 'unknown'
        end as event_name,
        try_to_timestamp(normalized_iso) as event_at,
        event_received_at,
        location_zip,
        raw_payload,
        case
            when event_at_raw rlike '^[0-9]{8}T[0-9]{6}$' then true
            when event_at_raw rlike '^[0-9]{4}/[0-9]{2}/[0-9]{2}' then true
            when event_at_raw rlike '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then true
            when try_to_timestamp(normalized_iso) is null then true
            else false
        end as is_malformed_timestamp,
        case when event_code is null and event_type is null then true else false end as is_missing_event_type,
        current_timestamp() as inserted_at
    from normalized
)

select
    pe.*,
    case when l.voided_at is not null then true else false end as is_event_on_voided_label
from parsed_events pe
left join {{ ref('labels') }} l on pe.label_id = l.label_id
