import pyodbc

CONN = ("DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;"
        "DATABASE=support_intelligence;Trusted_Connection=yes;")

QUERIES = {
    "Source health": """
        SELECT span_name,
               COUNT(*) AS calls,
               SUM(CASE WHEN source_ok = 0 THEN 1 ELSE 0 END) AS failures,
               CAST(AVG(duration_ms) AS DECIMAL(10,2)) AS avg_ms
        FROM dbo.TRACES
        WHERE kind = 'tool'
        GROUP BY span_name
        ORDER BY failures DESC, span_name
    """,
    "Model cost": """
        SELECT span_name,
               COUNT(*) AS calls,
               SUM(tokens_in) AS tokens_in,
               SUM(tokens_out) AS tokens_out,
               CAST(AVG(duration_ms) AS DECIMAL(10,1)) AS avg_ms
        FROM dbo.TRACES
        WHERE kind = 'llm'
        GROUP BY span_name
    """,
}

with pyodbc.connect(CONN) as conn:
    cur = conn.cursor()
    for title, sql in QUERIES.items():
        print(f"\n{title}")
        print("-" * 60)
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        print("  ".join(f"{c:<14}" for c in cols))
        for row in cur.fetchall():
            print("  ".join(f"{str(v):<14}" for v in row))
