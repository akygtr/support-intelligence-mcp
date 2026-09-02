import pyodbc

CONN = ("DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;"
        "DATABASE=master;Trusted_Connection=yes;")

with pyodbc.connect(CONN, autocommit=True) as conn:
    cur = conn.cursor()
    cur.execute("""
        IF DB_ID('support_intelligence') IS NULL
            CREATE DATABASE support_intelligence
    """)
    print("database ready")

CONN_DB = CONN.replace("DATABASE=master", "DATABASE=support_intelligence")

with pyodbc.connect(CONN_DB, autocommit=True) as conn:
    cur = conn.cursor()
    cur.execute("""
        IF OBJECT_ID('dbo.TRACES', 'U') IS NULL
        CREATE TABLE dbo.TRACES (
            trace_id      INT IDENTITY(1,1) PRIMARY KEY,
            run_id        VARCHAR(32)   NOT NULL,
            case_id       VARCHAR(64),
            span_name     VARCHAR(64)   NOT NULL,
            kind          VARCHAR(16)   NOT NULL,
            started_at    DATETIME2     NOT NULL,
            duration_ms   FLOAT         NOT NULL,
            ok            BIT           NOT NULL,
            error         NVARCHAR(400),
            source_ok     BIT,
            source_error  NVARCHAR(400),
            bytes         INT,
            hits          INT,
            tokens_in     INT,
            tokens_out    INT,
            provider      VARCHAR(32),
            attempt       INT,
            loaded_at     DATETIME2     DEFAULT SYSUTCDATETIME()
        )
    """)
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_TRACES_run')
            CREATE INDEX IX_TRACES_run ON dbo.TRACES (run_id, span_name)
    """)
    print("table ready")
