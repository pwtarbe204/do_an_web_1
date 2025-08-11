import psycopg2

def connect(DB_HOST, DB_DATABASE, DB_USERNAME, DB_PASSWORD):
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_DATABASE,
            user=DB_USERNAME,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()
        return conn, cursor
    except psycopg2.Error as e:
        print("❌ PostgreSQL connection error:", e)
        return None, None