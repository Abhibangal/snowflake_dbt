select * from {{ source('postgres','assoc_quotes_companies') }}
