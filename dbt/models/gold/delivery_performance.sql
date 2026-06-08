-- Gold operational mart: one row per label with the on-time delivery metric.

with latest_delivery_per_label as (
    -- Latest 'delivered' event per label (defensive dedup via window function)
    select
        label_id,
        event_at,
        row_number() over (partition by label_id order by event_at desc) as rn
    from {{ ref('tracking_events') }}
    where event_name = 'delivered'
),

delivery_data as (
    select
        label_id,
        event_at as actual_delivery_at
    from latest_delivery_per_label
    where rn = 1
)

select
    -- Dimensions
    l.label_id,
    l.customer_id,
    l.carrier,
    l.service_class,
    l.origin_zip,
    l.dest_zip,
    -- Facts
    l.label_created_at,
    l.carrier_promised_delivery_at,
    d.actual_delivery_at,
    -- Metrics
    case when d.actual_delivery_at is not null then true else false end as is_delivered,
    case
        when d.actual_delivery_at is not null and d.actual_delivery_at <= l.carrier_promised_delivery_at then true
        else false
    end as is_delivered_on_time,
    current_timestamp() as inserted_at
from {{ ref('labels') }} l
left join delivery_data d on l.label_id = d.label_id
