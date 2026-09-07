{{
config(
materialized = 'incremental',
incremental_strategy = 'append',
transient = false
)
}}
select 
        quote_id
        ,is_archived
        ,create_at created_dt
        ,updated_at updated_dt
        ,url
        ,hs_status status
        ,hs_payment_status payment_status
        ,date(hs_payment_date) payment_dt
        ,date(hs_expiration_date) expiration_dt
        ,coalesce(hs_render_status,'')render_status
        ,hs_tcv tcv
        ,hs_title title
        ,hs_quote_amount quote_amount
        ,date(load_time) load_dt        

from {{ source('postgres','parsed_quotes') }}
{% if is_incremental() %}
where load_time > (select coalesce(max(load_time),to_timestamp('2010-01-01')) from {{ this }})
{% endif %}