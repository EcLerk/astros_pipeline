CREATE TABLE IF NOT EXISTS astros_raw
(
    payload      String,
    _inserted_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(_inserted_at)
ORDER BY payload;

CREATE TABLE IF NOT EXISTS people
(
    craft        String,
    name         String,
    _inserted_at DateTime64(3)
)
ENGINE = ReplacingMergeTree(_inserted_at)
ORDER BY (craft, name);

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_raw_to_people
TO people
AS
SELECT
    JSONExtractString(person, 'craft') AS craft,
    JSONExtractString(person, 'name')  AS name,
    _inserted_at
FROM astros_raw
ARRAY JOIN JSONExtractArrayRaw(payload, 'people') AS person;