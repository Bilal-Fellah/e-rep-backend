import psycopg2

conn = psycopg2.connect(
    host="135.181.66.165",   # your VPS IP
    port=5432,
    database="erep-db",
    user="bilal",
    password="bilal7230"
)
cursor = conn.cursor()


cursor.execute("SELECT NOW();")
print(cursor.fetchone())
