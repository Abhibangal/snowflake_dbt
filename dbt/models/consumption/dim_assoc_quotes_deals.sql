{{
config(
materialized = 'incremental',
schema = 'analytics',
incremental_strategy = 'merge',
unique_key=['quote_id','deal_id'],
)
}}
select  * 
        ,current_date() as load_dt
from {{ ref('assoc_quotes_deals') }}
qualify row_number() over (
    partition by quote_id, deal_id
    order by updated_dt desc
) = 1