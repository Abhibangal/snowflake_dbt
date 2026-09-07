{{
config(
materialized = 'incremental',
transient = true
)
}}
select * from {{ source('postgres','invoice_relation') }}