{{
config(
materialized = 'incremental',
schema = 'analtyics',
incremental_strategy = 'merge',
unique_key='INVOICE_ID'
)
}}

select * from {{ ref('invoice_relation') }}