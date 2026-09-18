{{
config(
materialized = 'table',
schema = 'analytics'
)
}}

select  * 
        ,current_date() as load_dt
from {{ ref('assoc_quotes_companies') }}