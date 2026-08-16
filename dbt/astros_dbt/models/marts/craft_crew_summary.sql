{{
    config(
        materialized='table',
        engine='MergeTree()',
        order_by='(craft)'
    )
}}

-- Mart: how many people are currently on each spacecraft/station, and who they are.
-- Built on top of the already-deduplicated stg_people, so this is just
-- a plain GROUP BY, with no additional dedup logic needed.

select
    craft,
    count(*)                           as crew_size,
    arraySort(groupArray(name))        as crew_members,
    max(_inserted_at)                  as last_seen_at,
    now64(3)                           as _dbt_updated_at
from {{ ref('stg_people') }}
group by craft
order by crew_size desc
