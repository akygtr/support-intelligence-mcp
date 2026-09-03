from src.tools.snowflake import RawQueryInput

cases = [
    ("SELECT * FROM CUSTOMERS", True),
    ("DROP TABLE CUSTOMERS", False),
    ("SELECT * FROM CUSTOMERS; DROP TABLE CUSTOMERS", False),
    ("SELECT * FROM C WHERE x=1 UNION SELECT * FROM D", True),
    ("  select name from customers  ", True),
    ("DELETE FROM CUSTOMERS", False),
]

for sql, should_pass in cases:
    try:
        RawQueryInput(sql=sql)
        got = True
        note = ""
    except Exception as e:
        got = False
        note = str(e).split("\n")[-2].strip() if "\n" in str(e) else str(e)
    mark = "ok " if got == should_pass else "FAIL"
    print(f"{mark} {'allowed' if got else 'blocked':<8} {sql[:50]}")
