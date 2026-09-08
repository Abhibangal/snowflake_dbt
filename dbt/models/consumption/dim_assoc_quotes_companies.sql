{{
config(
materialized = 'incremental',
schema = 'analtyics',
incremental_strategy = 'merge',
unique_key=['quote_id','company_id']
)
}}

select * from {{ ref('assoc_quotes_companies') }}