{{
    config(
        materialized='view'
    )
}}

-- ReplacingMergeTree only deduplicates rows after MERGE/OPTIMIZE,
-- so on read we don't rely on the background merge having already run —
-- instead we explicitly take the latest version of each row by key (craft, name).
-- This is exactly the same logic the people table's engine uses
-- (ORDER BY (craft, name)), just made explicit in SQL.

with source as (

    select
        craft,
        name,
        _inserted_at
    from {{ source('astros', 'people') }}

),

deduped as (

    select
        craft,
        name,
        max(_inserted_at) as _inserted_at
    from source
    group by craft, name

)

select *
from deduped
