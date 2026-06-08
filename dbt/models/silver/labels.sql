-- Silver labels: collapse CDC rows to the latest state per label_id and add
-- data-quality / fraud flags. Ported from notebooks/silver_layer.py (Step 1).

with latest_per_label as (
    select
        *,
        row_number() over (partition by label_id order by last_updated_at desc) as rn
    from {{ source('raw', 'labels') }}
)

select
    label_id,
    customer_id,
    carrier,
    service_class,
    origin_zip,
    dest_zip,
    weight_oz,
    declared_value_cents,
    label_created_at,
    carrier_promised_delivery_at,
    voided_at,
    last_updated_at,
    -- Fraud / quality flags
    case when weight_oz between 1000 and 1120 then true else false end as can_be_weight_fraud,
    case
        when voided_at is not null and (voided_at - label_created_at) > interval 1 days then true
        else false
    end as can_be_void_fraud,
    case when declared_value_cents = 0 and declared_value_cents is not null then true else false end as can_be_insurance_anomaly,
    case when origin_zip is null or dest_zip is null then true else false end as can_be_missing_zip,
    current_timestamp() as inserted_at
from latest_per_label
where rn = 1
