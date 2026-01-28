"""
CSV Loader and Validator for Home Loan NBA Agent System.
Handles CSV parsing, schema validation, and error reporting.
"""

import pandas as pd
import io
from typing import Tuple, List, Optional
from pydantic import ValidationError as PydanticValidationError

from schemas import (
    LoanInput, 
    ValidationError, 
    CSVValidationResult,
)


# Expected column names in the CSV
REQUIRED_COLUMNS = [
    "loan_id",
    "secured_unsecured",
    "dpd",
    "outstanding_amount",
    "borrower_type",
    "employment_stability",
    "repayment_history",
    "loan_vintage_months",
    "collateral_quality",
    "geographic_location",
    "pincode",
    "customer_responsiveness",
    "cost_of_recovery",
    "expected_recovery",
    "time_value_recovery_months",
    "regulatory_constraints",
    "bank_portfolio_strategy",
    "jurisdiction",
    "cibil_score",
    "loan_officer_remarks",
    "documentation_type",
]

# Column type expectations for validation messages (flexible descriptions)
COLUMN_TYPES = {
    "loan_id": "string (unique identifier)",
    "secured_unsecured": "Secured or Unsecured",
    "dpd": "integer >= 0 (Days Past Due)",
    "outstanding_amount": "positive number (amount in INR)",
    "borrower_type": "string (e.g., Individual, Corporate, Salaried, Self-employed)",
    "employment_stability": "string (e.g., Stable, Moderate, Unstable)",
    "repayment_history": "string (e.g., Excellent, Good, Irregular, Poor)",
    "loan_vintage_months": "integer >= 0",
    "collateral_quality": "string (e.g., High, Medium, Low)",
    "geographic_location": "string (e.g., Metro, Urban, Tier-1, Tier-2, Rural)",
    "pincode": "6-digit number string",
    "customer_responsiveness": "string (e.g., High, Medium, Low, Cooperative, Non-responsive)",
    "cost_of_recovery": "number >= 0",
    "expected_recovery": "number >= 0",
    "time_value_recovery_months": "integer >= 0",
    "regulatory_constraints": "string (can be 'None')",
    "bank_portfolio_strategy": "string",
    "jurisdiction": "string (DRT/state jurisdiction)",
    "cibil_score": "integer between 300 and 900",
    "loan_officer_remarks": "string",
    "documentation_type": "string (e.g., Complete, Incomplete, Partial, Missing)",
}


def check_missing_columns(df: pd.DataFrame) -> List[str]:
    """Check for missing required columns in DataFrame."""
    df_columns = [col.strip().lower().replace(' ', '_') for col in df.columns]
    missing = []
    for col in REQUIRED_COLUMNS:
        if col.lower() not in df_columns:
            missing.append(col)
    return missing


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names to match expected schema."""
    df.columns = [col.strip().lower().replace(' ', '_') for col in df.columns]
    return df


def coerce_value(value, column_name: str):
    """Attempt to coerce value to expected type."""
    if pd.isna(value) or value == '' or str(value).strip().lower() in ['nan', 'none', 'null', '']:
        # Default values for fields that can be empty/None
        defaults = {
            'regulatory_constraints': 'None',
            'loan_officer_remarks': '',
            'customer_responsiveness': 'Non-responsive',  # Safe default
            'documentation_type': 'Incomplete',  # Safe default
        }
        if column_name in defaults:
            return defaults[column_name]
        return None
    
    # String columns
    if column_name in ['loan_id', 'regulatory_constraints', 'bank_portfolio_strategy', 
                       'jurisdiction', 'loan_officer_remarks', 'secured_unsecured',
                       'borrower_type', 'employment_stability', 'repayment_history',
                       'collateral_quality', 'geographic_location', 'customer_responsiveness',
                       'documentation_type']:
        return str(value).strip()
    
    # Pincode - ensure it's a 6-digit string
    if column_name == 'pincode':
        val = str(value).strip()
        # Remove any decimal point (Excel sometimes adds .0)
        if '.' in val:
            val = val.split('.')[0]
        return val.zfill(6) if len(val) < 6 else val
    
    # Integer columns
    if column_name in ['dpd', 'loan_vintage_months', 'time_value_recovery_months', 'cibil_score']:
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return value
    
    # Float columns
    if column_name in ['outstanding_amount', 'cost_of_recovery', 'expected_recovery']:
        try:
            return float(value)
        except (ValueError, TypeError):
            return value
    
    # Default - return as string
    return str(value).strip()


def validate_row(row_data: dict, row_number: int) -> Tuple[Optional[LoanInput], List[ValidationError]]:
    """
    Validate a single row of CSV data against the LoanInput schema.
    
    Returns:
        Tuple of (validated LoanInput or None, list of validation errors)
    """
    errors = []
    loan_id = row_data.get('loan_id', f'Row_{row_number}')
    
    # Coerce values to expected types
    coerced_data = {}
    for col in REQUIRED_COLUMNS:
        value = row_data.get(col)
        coerced_data[col] = coerce_value(value, col)
    
    # Attempt Pydantic validation
    try:
        loan = LoanInput(**coerced_data)
        return loan, []
    except PydanticValidationError as e:
        for error in e.errors():
            field = error['loc'][0] if error['loc'] else 'unknown'
            errors.append(ValidationError(
                row_number=row_number,
                loan_id=str(loan_id),
                column_name=str(field),
                error_message=error['msg'],
                provided_value=str(coerced_data.get(field, 'N/A'))
            ))
        return None, errors


def load_and_validate_csv(file_content: bytes, filename: str) -> CSVValidationResult:
    """
    Load and validate a CSV file.
    
    Args:
        file_content: Raw bytes of the CSV file
        filename: Name of the file for error messages
        
    Returns:
        CSVValidationResult with validation status and parsed loans
    """
    errors = []
    valid_loans = []
    
    # Check if content is empty
    if not file_content or len(file_content.strip()) == 0:
        return CSVValidationResult(
            is_valid=False,
            valid_loans=[],
            errors=[ValidationError(
                row_number=0,
                loan_id=None,
                column_name="file",
                error_message="File is empty",
                provided_value=filename
            )],
            total_rows=0,
            valid_count=0,
            error_count=1
        )
    
    # Try to read CSV
    df = None
    try:
        # Try different encodings
        for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
            try:
                df = pd.read_csv(io.BytesIO(file_content), encoding=encoding)
                if df is not None and not df.empty:
                    break
            except (UnicodeDecodeError, pd.errors.EmptyDataError):
                continue
        
        if df is None or df.empty:
            return CSVValidationResult(
                is_valid=False,
                valid_loans=[],
                errors=[ValidationError(
                    row_number=0,
                    loan_id=None,
                    column_name="file",
                    error_message="Unable to read file - file may be empty or corrupted",
                    provided_value=filename
                )],
                total_rows=0,
                valid_count=0,
                error_count=1
            )
    except Exception as e:
        return CSVValidationResult(
            is_valid=False,
            valid_loans=[],
            errors=[ValidationError(
                row_number=0,
                loan_id=None,
                column_name="file",
                error_message=f"Failed to parse CSV: {str(e)}",
                provided_value=filename
            )],
            total_rows=0,
            valid_count=0,
            error_count=1
        )
    
    # Remove completely empty rows
    df = df.dropna(how='all')
    
    if df.empty:
        return CSVValidationResult(
            is_valid=False,
            valid_loans=[],
            errors=[ValidationError(
                row_number=0,
                loan_id=None,
                column_name="file",
                error_message="No data rows found in file",
                provided_value=filename
            )],
            total_rows=0,
            valid_count=0,
            error_count=1
        )
    
    # Normalize column names
    df = normalize_column_names(df)
    
    # Check for missing columns
    missing_cols = check_missing_columns(df)
    if missing_cols:
        for col in missing_cols:
            errors.append(ValidationError(
                row_number=0,
                loan_id=None,
                column_name=col,
                error_message=f"Missing required column. Expected type: {COLUMN_TYPES.get(col, 'unknown')}",
                provided_value="MISSING"
            ))
        return CSVValidationResult(
            is_valid=False,
            valid_loans=[],
            errors=errors,
            total_rows=len(df),
            valid_count=0,
            error_count=len(errors)
        )
    
    # Validate each row
    total_rows = len(df)
    for idx, row in df.iterrows():
        row_number = idx + 2  # +2 because of 0-indexing and header row
        row_data = row.to_dict()
        
        loan, row_errors = validate_row(row_data, row_number)
        
        if loan:
            valid_loans.append(loan)
        else:
            errors.extend(row_errors)
    
    return CSVValidationResult(
        is_valid=len(errors) == 0,
        valid_loans=valid_loans,
        errors=errors,
        total_rows=total_rows,
        valid_count=len(valid_loans),
        error_count=len(errors)
    )


def format_validation_errors(result: CSVValidationResult) -> str:
    """Format validation errors for display in UI."""
    if result.is_valid:
        return f"✅ All {result.valid_count} rows validated successfully."
    
    output = f"❌ Validation failed: {result.error_count} error(s) in {result.total_rows} rows\n\n"
    
    # Group errors by row
    errors_by_row = {}
    for error in result.errors:
        if error.row_number not in errors_by_row:
            errors_by_row[error.row_number] = []
        errors_by_row[error.row_number].append(error)
    
    for row_num, row_errors in errors_by_row.items():
        if row_num == 0:
            output += "**File-level errors:**\n"
        else:
            loan_id = row_errors[0].loan_id or f"Row {row_num}"
            output += f"**Row {row_num}** (Loan: {loan_id}):\n"
        
        for error in row_errors:
            output += f"  - `{error.column_name}`: {error.error_message}\n"
            output += f"    Provided: `{error.provided_value}`\n"
        output += "\n"
    
    return output


def get_preview_dataframe(file_content: bytes, num_rows: int = 5) -> Tuple[Optional[pd.DataFrame], str]:
    """
    Get a preview of the CSV file.
    
    Returns:
        Tuple of (DataFrame preview or None, error message if any)
    """
    # Check if content is empty
    if not file_content or len(file_content.strip()) == 0:
        return None, "File is empty"
    
    try:
        for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
            try:
                df = pd.read_csv(io.BytesIO(file_content), encoding=encoding)
                if df is not None and not df.empty:
                    # Remove completely empty rows
                    df = df.dropna(how='all')
                    return df.head(num_rows), ""
            except (UnicodeDecodeError, pd.errors.EmptyDataError):
                continue
        return None, "Unable to read file with any supported encoding"
    except Exception as e:
        return None, f"Failed to parse CSV: {str(e)}"
