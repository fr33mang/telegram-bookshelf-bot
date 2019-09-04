import os
import psycopg2

DATABASE_URL = os.environ['DATABASE_URL']

conn = psycopg2.connect(DATABASE_URL, sslmode='require')

cur = conn.cursor()
# cur.execute("DROP TABLE tokens;")
cur.execute("CREATE TABLE IF NOT EXISTS tokens ("
            "   id INTEGER PRIMARY KEY,"
            "   request_token VARCHAR,"
            "   request_token_secret VARCHAR,"
            "   access_token VARCHAR,"
            "   access_token_secret VARCHAR,"
            "   goodreads_id INTEGER)")
cur.close()
conn.commit()
