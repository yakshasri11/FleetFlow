import sys
from sqlalchemy import create_engine, text

url = sys.argv[1]
engine = create_engine(url)

with engine.connect() as conn:
    tables = conn.execute(text("""
        SELECT tablename FROM pg_tables WHERE schemaname = 'public'
    """)).fetchall()
    table_names = [t[0] for t in tables]
    if table_names:
        joined = ", ".join(f'"{t}"' for t in table_names)
        conn.execute(text(f"TRUNCATE {joined} RESTART IDENTITY CASCADE"))
        conn.commit()
        print(f"Truncated and reset ID counters for: {table_names}")
    else:
        print("No tables found.")
