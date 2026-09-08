{{
config(
materialized = 'incremental',
schema = 'analytics',
incremental_strategy = 'merge',
unique_key='INVOICE_ID'
)
}}

select * from {{ ref('invoice_relation') }}