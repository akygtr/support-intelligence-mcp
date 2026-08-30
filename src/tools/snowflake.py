import os
import json
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from src.fixtures import is_mock, load
import snowflake.connector

load_dotenv()

mcp = FastMCP("snowflake_mcp")

# Pull all connection params from .env
SNOWFLAKE_CONFIG = {
    "account":   os.getenv("SNOWFLAKE_ACCOUNT"),    # e.g. xy12345.us-east-1
    "user":      os.getenv("SNOWFLAKE_USER"),
    "password":  os.getenv("SNOWFLAKE_PASSWORD"),
    "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
    "database":  os.getenv("SNOWFLAKE_DATABASE"),
    "schema":    os.getenv("SNOWFLAKE_SCHEMA"),
}


def _get_connection():
    """Return an authenticated Snowflake connection."""
    missing = [k for k, v in SNOWFLAKE_CONFIG.items() if not v]
    if missing:
        raise ValueError(f"Missing Snowflake env vars: {', '.join('SNOWFLAKE_' + k.upper() for k in missing)}")

    return snowflake.connector.connect(**SNOWFLAKE_CONFIG)


def _run_query(sql: str, params: tuple = ()) -> list[dict]:
    """Execute a SQL query and return rows as list of dicts."""
    conn = _get_connection()
    try:
        cursor = conn.cursor(snowflake.connector.DictCursor)
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        conn.close()


class CustomerQueryInput(BaseModel):
    """Input model for customer data lookup tool."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )

    customer_name: str = Field(
        ...,
        description="Customer or company name to look up (partial match supported)",
        min_length=1,
        max_length=200
    )
    max_results: Optional[int] = Field(
        default=5,
        description="Max rows to return (1-50)",
        ge=1,
        le=50
    )


class RawQueryInput(BaseModel):
    """Input model for raw SQL query tool."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )

    sql: str = Field(
        ...,
        description="Read-only SQL query to run against Snowflake (SELECT only)",
        min_length=10,
        max_length=2000
    )


@mcp.tool(
    name="query_customer_data",
    annotations={
        "title": "Query Customer Account Data",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def query_customer_data(params: CustomerQueryInput, ticket_id: str = "") -> str:
    """Look up customer account info from Snowflake by company name.

    Searches the CUSTOMERS table for matching accounts and returns
    account details, contract info, and customer history.

    Args:
        params (CustomerQueryInput): Validated input with:
            - customer_name (str): Company name to search (partial match)
            - max_results (int): Max rows to return (default 5)
        ticket_id (str): Optional. Used to select the fixture in mock mode.

    Returns:
        str: JSON with matching customer records. Each record contains
             whatever columns exist in your CUSTOMERS table.
             Returns empty list if no matches found.
    """
    if is_mock():
        return json.dumps(load("snowflake", ticket_id or params.customer_name))

    try:
        sql = """
            SELECT *
            FROM CUSTOMERS
            WHERE UPPER(NAME) LIKE UPPER(%s)
            OR UPPER(COMPANY) LIKE UPPER(%s)
            LIMIT %s
        """
        rows = _run_query(
            sql,
            (f"%{params.customer_name}%", f"%{params.customer_name}%", params.max_results)
        )
        serializable = []
        for row in rows:
            serializable.append({
                k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
                for k, v in row.items()
            })
        return json.dumps({
            "customer_name": params.customer_name,
            "count": len(serializable),
            "records": serializable
        }, indent=2)
    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"Snowflake query failed: {str(e)}"})


@mcp.tool(
    name="run_snowflake_query",
    annotations={
        "title": "Run Raw SQL Query on Snowflake",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def run_snowflake_query(params: RawQueryInput) -> str:
    """Execute a custom read-only SQL query against Snowflake.

    Use this for flexible ad-hoc queries beyond the standard customer lookup.
    Only SELECT statements are permitted.

    Args:
        params (RawQueryInput): Validated input with:
            - sql (str): Valid SELECT SQL query

    Returns:
        str: JSON with query results as list of row dicts,
             plus row count. Returns error if query is not SELECT.
    """
    if not params.sql.strip().upper().startswith("SELECT"):
        return json.dumps({"error": "Only SELECT queries are permitted."})

    try:
        rows = _run_query(params.sql)
        serializable = []
        for row in rows:
            serializable.append({
                k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
                for k, v in row.items()
            })
        return json.dumps({
            "count": len(serializable),
            "rows": serializable
        }, indent=2)
    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"Snowflake query failed: {str(e)}"})
