import pyodbc

CONN = ("DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;"
        "DATABASE=support_intelligence;Trusted_Connection=yes;")

VIEWS = {
"V_SOURCE_HEALTH": """
SELECT
    run_id,
    span_name                                              AS source_name,
    COUNT(*)                                               AS calls,
    SUM(CASE WHEN source_ok = 0 THEN 1 ELSE 0 END)         AS failures,
    CAST(100.0 * SUM(CASE WHEN source_ok = 0 THEN 1 ELSE 0 END)
         / COUNT(*) AS DECIMAL(5,2))                       AS failure_pct,
    CAST(AVG(duration_ms) AS DECIMAL(10,2))                AS avg_ms,
    CAST(MAX(duration_ms) AS DECIMAL(10,2))                AS max_ms,
    AVG(CAST(bytes AS FLOAT))                              AS avg_bytes,
    MIN(started_at)                                        AS run_started
FROM dbo.TRACES
WHERE kind = 'tool'
GROUP BY run_id, span_name
""",

"V_RUN_COST": """
SELECT
    run_id,
    MIN(started_at)                          AS run_started,
    COUNT(*)                                 AS model_calls,
    SUM(tokens_in)                           AS tokens_in,
    SUM(tokens_out)                          AS tokens_out,
    CAST(AVG(duration_ms) AS DECIMAL(10,1))  AS avg_latency_ms,
    CAST(MAX(duration_ms) AS DECIMAL(10,1))  AS max_latency_ms,
    CAST(SUM(tokens_in)  / 1000000.0 * 1.00
       + SUM(tokens_out) / 1000000.0 * 5.00 AS DECIMAL(10,5)) AS est_cost_usd
FROM dbo.TRACES
WHERE kind = 'llm'
GROUP BY run_id
""",

"V_TIME_SPLIT": """
SELECT
    run_id,
    MIN(started_at)                                                   AS run_started,
    SUM(CASE WHEN kind = 'tool' THEN duration_ms ELSE 0 END)          AS retrieval_ms,
    SUM(CASE WHEN kind = 'llm'  THEN duration_ms ELSE 0 END)          AS generation_ms,
    SUM(duration_ms)                                                  AS total_ms
FROM dbo.TRACES
GROUP BY run_id
""",

"V_FAILURES": """
SELECT
    run_id,
    case_id,
    span_name        AS source_name,
    started_at,
    LEFT(source_error, 200) AS error_message
FROM dbo.TRACES
WHERE source_ok = 0
""",
}

with pyodbc.connect(CONN, autocommit=True) as conn:
    cur = conn.cursor()
    for name, sql in VIEWS.items():
        cur.execute(f"IF OBJECT_ID('dbo.{name}', 'V') IS NOT NULL DROP VIEW dbo.{name}")
        cur.execute(f"CREATE VIEW dbo.{name} AS {sql}")
        print(f"created dbo.{name}")
