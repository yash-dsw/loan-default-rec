"""
Script to create the loan_delinquency_cases table and import data from CSV.
Run this script to set up the database with initial data.

Usage:
    python import_csv_to_db.py <path_to_csv>
    
Example:
    python import_csv_to_db.py test_input.csv
"""

import os
import sys
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

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


# SQL to create the table matching LoanInput schema
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS loan_delinquency_cases (
    account_id VARCHAR(50) PRIMARY KEY,
    customer_id VARCHAR(50) NOT NULL,
    customer_full_name VARCHAR(100) NOT NULL,

    -- Loan Details
    loan_type VARCHAR(50) NOT NULL,
    secured_flag VARCHAR(15) CHECK (secured_flag IN ('Secured', 'Unsecured')),
    collateral_type VARCHAR(50),
    collateral_quality VARCHAR(100),
    collateral_liquidity VARCHAR(50),

    loan_amount DECIMAL(15,2),
    outstanding_amount DECIMAL(15,2),
    emi_amount DECIMAL(12,2),
    tenure_months INT,
    loan_vintage_months INT,

    -- Customer Profile
    customer_type VARCHAR(30),
    geography VARCHAR(30),
    annual_income_total VARCHAR(20),
    interest_rate INT,

    -- Recovery Economics
    cost_of_recovery DECIMAL(12,2),
    expected_recovery DECIMAL(12,2),
    cibil_score INT,

    -- Delinquency & Behaviour
    dpd INT CHECK (dpd >= 90), -- NPA only
    contactability_score INT CHECK (contactability_score BETWEEN 0 AND 100),
    response_to_calls VARCHAR(20),
    field_visit_outcome VARCHAR(50),
    broken_promises_count INT DEFAULT 0,

    -- Collection Actions
    last_action_taken VARCHAR(30),
    days_since_last_action INT,

    call_done VARCHAR(10),
    field_visit_done VARCHAR(10),
    restructure_offered VARCHAR(10),
    restructure_accepted VARCHAR(10),

    legal_notice_sent VARCHAR(10),      -- SARFAESI 13(2)
    possession VARCHAR(10),             -- 13(4)
    auction VARCHAR(10),                -- Rule 8
    ots_offered VARCHAR(10),
    ots_accepted VARCHAR(10),

    -- Documentation & Charge Readiness
    chg_form_type VARCHAR(10),           -- CHG-1 / CHG-9
    hypothecation_deed_flag VARCHAR(10),
    sanction_letter_flag VARCHAR(10),
    charge_instrument_flag VARCHAR(10),
    borrower_response_logged VARCHAR(10),

    charge_registered_flag VARCHAR(10),
    dsc_available_flag VARCHAR(10),
    director_din_available VARCHAR(10),
    certificate_of_registration_flag VARCHAR(10),
    authorized_signatory_pan VARCHAR(10),
    cs_membership_no_flag VARCHAR(10),

    -- Final SARFAESI Readiness
    sarfaesi_ready_flag VARCHAR(10),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
 
"""


def create_table(conn):
    """Drop and recreate the loan_delinquency_cases table with the latest schema."""
    with conn.cursor() as cur:
        # Drop existing table to apply new schema
        cur.execute("DROP TABLE IF EXISTS loan_delinquency_cases CASCADE;")
        print("[INFO] Dropped existing table (if any) to apply new schema.")
        
        # Create table with new schema
        cur.execute(CREATE_TABLE_SQL)
        conn.commit()
    print("[OK] Table 'loan_delinquency_cases' created with updated schema.")


def import_csv(conn, csv_path: str):
    """Import data from CSV into the database."""
    
    # Read CSV
    df = pd.read_csv(csv_path)
    print(f"[INFO] Read {len(df)} rows from {csv_path}")
    
    # Map CSV columns to database columns (handle column name differences and typos)
    column_mapping = {
        # Step prefixed columns from old format
        'step_call_done': 'call_done',
        'step_field_visit_done': 'field_visit_done',
        'step_restructure_initiated': 'restructure_offered',
        'step_legal_notice_sent': 'legal_notice_sent',
        'step_possession': 'possession',
        'step_auction': 'auction',
        'step_ots_offered': 'ots_offered',
        'step_ots_accepted': 'ots_accepted',
        # Common typos in CSV headers
        'customer_full_Nome': 'customer_full_name',
        'authorized_sigNotory_pan': 'authorized_signatory_pan',
    }
    
    # Rename columns if they exist
    for old_name, new_name in column_mapping.items():
        if old_name in df.columns and new_name not in df.columns:
            df.rename(columns={old_name: new_name}, inplace=True)
    
    # Add default values for missing columns
    defaults = {
        'customer_full_name': 'Unknown Customer',
        'collateral_type': 'Property',
        'collateral_quality': 'Medium',
        'collateral_liquidity': 'Medium',
        'annual_income_total': 'Unknown',
        'interest_rate': 10,
        'cost_of_recovery': 50000,
        'expected_recovery': 0,
        'cibil_score': 650,
        'call_done': 'No',
        'field_visit_done': 'No',
        'restructure_accepted': 'No',
        'possession': 'No',
        'auction': 'No',
        'ots_accepted': 'No',
        'chg_form_type': 'CHG-1',
        'hypothecation_deed_flag': 'Yes',
        'sanction_letter_flag': 'Yes',
        'charge_instrument_flag': 'Yes',
        'borrower_response_logged': 'No',
        'charge_registered_flag': 'Yes',
        'dsc_available_flag': 'Yes',
        'director_din_available': 'N/A',
        'certificate_of_registration_flag': 'N/A',
        'authorized_signatory_pan': 'Yes',
        'cs_membership_no_flag': 'N/A',
        'sarfaesi_ready_flag': 'No',
    }
    
    for col, default_val in defaults.items():
        if col not in df.columns:
            df[col] = default_val
    
    # Define columns to insert (matching the table schema)
    insert_columns = [
        'account_id', 'customer_id', 'customer_full_name', 'loan_type', 'secured_flag',
        'collateral_type', 'collateral_quality', 'collateral_liquidity',
        'loan_amount', 'outstanding_amount', 'emi_amount', 'tenure_months', 'loan_vintage_months',
        'customer_type', 'geography', 'annual_income_total', 'interest_rate',
        'cost_of_recovery', 'expected_recovery', 'cibil_score',
        'dpd', 'contactability_score', 'response_to_calls', 'field_visit_outcome',
        'broken_promises_count', 'last_action_taken', 'days_since_last_action',
        'call_done', 'field_visit_done', 'restructure_offered', 'restructure_accepted',
        'legal_notice_sent', 'possession', 'auction', 'ots_offered', 'ots_accepted',
        'chg_form_type', 'hypothecation_deed_flag', 'sanction_letter_flag',
        'charge_instrument_flag', 'borrower_response_logged', 'charge_registered_flag',
        'dsc_available_flag', 'director_din_available', 'certificate_of_registration_flag',
        'authorized_signatory_pan', 'cs_membership_no_flag', 'sarfaesi_ready_flag'
    ]
    
    # Filter to only columns that exist in the DataFrame
    available_columns = [col for col in insert_columns if col in df.columns]
    
    # Prepare data for insertion
    records = df[available_columns].values.tolist()
    
    # Build INSERT statement
    columns_str = ', '.join(available_columns)
    placeholders = ', '.join(['%s'] * len(available_columns))
    
    insert_sql = f"""
        INSERT INTO loan_delinquency_cases ({columns_str})
        VALUES ({placeholders})
        ON CONFLICT (account_id) DO UPDATE SET
        {', '.join([f"{col} = EXCLUDED.{col}" for col in available_columns if col != 'account_id'])}
    """
    
    with conn.cursor() as cur:
        for record in records:
            cur.execute(insert_sql, record)
        conn.commit()
    
    print(f"[OK] Imported {len(records)} records into 'loan_delinquency_cases'.")


def main():
    if len(sys.argv) < 2:
        print("Usage: python import_csv_to_db.py <path_to_csv>")
        print("Example: python import_csv_to_db.py test_input.csv")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    
    if not os.path.exists(csv_path):
        print(f"[ERROR] File not found: {csv_path}")
        sys.exit(1)
    
    try:
        conn = get_db_connection()
        print("[OK] Connected to database.")
        
        # Create table
        create_table(conn)
        
        # Import CSV data
        import_csv(conn, csv_path)
        
        conn.close()
        print("[OK] Done!")
        
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
