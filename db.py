import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional
from dotenv import load_dotenv
from schemas import LoanInput

load_dotenv()

def get_db_connection():
    """Establish a connection to the PostgreSQL database."""
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        port=os.getenv("DB_PORT")
    )
    return conn

def get_loan_by_id(account_id: str) -> Optional[LoanInput]:
    """
    Fetch a loan record from the database by account_id and map it to LoanInput.
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = "SELECT * FROM loan_delinquency_cases WHERE account_id = %s"
            cur.execute(query, (account_id,))
            row = cur.fetchone()
            
            if not row:
                return None
            
            # Map DB row to LoanInput using model_validate
            # We convert decimals to floats, datetimes to strings
            clean_row = {}
            for k, v in row.items():
                if hasattr(v, '__float__') and not isinstance(v, (int, float)):
                    clean_row[k] = float(v)
                elif hasattr(v, 'isoformat'):  # Handle datetime objects
                    clean_row[k] = v.isoformat() if v else None
                else:
                    clean_row[k] = v
            
            # Additional logic for derived fields if necessary
            # Note: LoanInput uses aliases (e.g., loan_id -> account_id) so we can pass clean_row directly
            return LoanInput.model_validate(clean_row)
            
    except Exception as e:
        print(f"Database error: {e}")
        raise e
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # Test connection
    try:
        connection = get_db_connection()
        print("✅ Database connection successful!")
        connection.close()
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
