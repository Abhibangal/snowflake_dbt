{{
config(
materialized = 'incremental',
schema = 'analytics',
incremental_strategy = 'merge',
unique_key='INVOICE_ID'
)
}}

select  * 
        ,current_date() as load_dt
from {{ ref('invoice_relation') }}