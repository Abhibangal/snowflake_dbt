{{
config(
materialized = 'incremental',
schema = 'analytics',
incremental_strategy = 'merge',
unique_key=['quote_id','company_id']
)
}}

select  * 
        ,current_date() as load_dt
from {{ ref('assoc_quotes_companies') }}