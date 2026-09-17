{{
config(
materialized = 'incremental',
schema = 'analytics',
incremental_strategy = 'merge',
unique_key=['deal_id','quote_id']
)
}}

select      deal_id
            ,quote_id
            ,amount
            ,acv 
            ,arr
            ,created_dt
            ,updated_at updated_dt
            ,closed_Dt
            ,current_date() as load_dt

from {{ ref('deals') }}