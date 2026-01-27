"""
Input Validators for NBA Decision System
Validates CSV input and loan data against expected schema
"""

import pandas as pd
from typing import Tuple, List, Dict, Any, Optional


# Required columns in the input CSV
REQUIRED_COLUMNS = [
    "account_id", "customer_id", "loan_type", "secured_flag",
    "loan_amount", "outstanding_amount", "emi_amount", "tenure_months", "loan_vintage_months",
    "customer_type", "geography", "co_borrower_present", "income_band", "credit_score_band",
    "dpd", "delinquency_stage", "times_delinquent", "max_dpd_ever", "last_payment_days_ago",
    "contactability_score", "response_to_calls", "field_visit_outcome", "broken_promises_count",
    "fraud_flag", "last_action_taken", "days_since_last_action",
    "legal_notice_sent", "sarfaesi_stage", "restructure_offered", "ots_offered", "action_accepted",
    "recovery_amount_30d", "recovery_amount_90d", "account_resolved", "resolution_type",
    "step_call_done", "step_field_visit_done", "step_restructure_initiated", "step_legal_notice_sent",
    "step_sarfaesi_invoked", "step_possession", "step_auction", "step_ots_offered", "step_ots_accepted"
]

# Valid values for categorical columns
VALID_VALUES = {
    "loan_type": ["Home", "Vehicle", "Personal", "Business", "Education"],
    "secured_flag": ["Secured", "Unsecured"],
    "customer_type": ["Salaried", "Self-employed", "Corporate"],
    "geography": ["Urban", "Semi-urban", "Rural"],
    "co_borrower_present": ["Yes", "No"],
    "income_band": ["Low", "Medium", "High"],
    "credit_score_band": ["Poor", "Fair", "Good", "Excellent"],
    "delinquency_stage": ["SMA-0", "SMA-1", "SMA-2", "NPA"],
    "response_to_calls": ["Positive", "Delayed", "None"],
    "field_visit_outcome": ["Promise to Pay", "Refused", "Not Done"],
    "fraud_flag": ["Yes", "No"],
    "legal_notice_sent": ["Yes", "No"],
    "sarfaesi_stage": ["None", "13(2)", "13(4)", "Possession", "Auction"],
    "restructure_offered": ["Yes", "No"],
    "ots_offered": ["Yes", "No"],
    "action_accepted": ["Yes", "No"],
    "account_resolved": ["Yes", "No"],
    "step_call_done": ["Yes", "No"],
    "step_field_visit_done": ["Yes", "No"],
    "step_restructure_initiated": ["Yes", "No"],
    "step_legal_notice_sent": ["Yes", "No"],
    "step_sarfaesi_invoked": ["Yes", "No"],
    "step_possession": ["Yes", "No"],
    "step_auction": ["Yes", "No"],
    "step_ots_offered": ["Yes", "No"],
    "step_ots_accepted": ["Yes", "No"]
}

# Numeric columns with their expected ranges
NUMERIC_RANGES = {
    "loan_amount": (10000, 100000000),  # 10K to 10Cr
    "outstanding_amount": (0, 100000000),
    "emi_amount": (100, 10000000),
    "tenure_months": (1, 360),  # 1 month to 30 years
    "loan_vintage_months": (0, 360),
    "dpd": (0, 1000),
    "times_delinquent": (0, 100),
    "max_dpd_ever": (0, 1000),
    "last_payment_days_ago": (0, 1000),
    "contactability_score": (0, 100),
    "broken_promises_count": (0, 50),
    "days_since_last_action": (0, 365),
    "recovery_amount_30d": (0, 100000000),
    "recovery_amount_90d": (0, 100000000)
}


class ValidationResult:
    """Result of validation process"""
    
    def __init__(self):
        self.is_valid = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.validated_data: Optional[pd.DataFrame] = None
    
    def add_error(self, error: str):
        """Add an error and mark as invalid"""
        self.is_valid = False
        self.errors.append(error)
    
    def add_warning(self, warning: str):
        """Add a warning (doesn't affect validity)"""
        self.warnings.append(warning)
    
    def get_summary(self) -> str:
        """Get validation summary"""
        lines = []
        
        if self.is_valid:
            lines.append("✅ Validation Passed")
        else:
            lines.append("❌ Validation Failed")
        
        if self.errors:
            lines.append("\n**Errors:**")
            for error in self.errors:
                lines.append(f"- {error}")
        
        if self.warnings:
            lines.append("\n**Warnings:**")
            for warning in self.warnings:
                lines.append(f"- {warning}")
        
        return "\n".join(lines)


def validate_csv_input(df: pd.DataFrame, max_rows: int = 5) -> ValidationResult:
    """
    Validate input CSV DataFrame against expected schema.
    
    Args:
        df: Input DataFrame from CSV
        max_rows: Maximum allowed rows (default 5)
    
    Returns:
        ValidationResult with status and any errors/warnings
    """
    result = ValidationResult()
    
    # Check row count
    if len(df) == 0:
        result.add_error("CSV file is empty")
        return result
    
    if len(df) > max_rows:
        result.add_warning(f"CSV has {len(df)} rows, only first {max_rows} will be processed")
        df = df.head(max_rows).copy()
    
    # Check required columns
    missing_columns = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing_columns:
        result.add_error(f"Missing required columns: {', '.join(missing_columns)}")
        return result
    
    # Validate each row
    for idx, row in df.iterrows():
        row_num = idx + 1
        account_id = row.get('account_id', f'Row {row_num}')
        
        # Validate categorical columns
        for col, valid_vals in VALID_VALUES.items():
            if col in df.columns:
                val = str(row[col]).strip() if pd.notna(row[col]) else ""
                if val and val not in valid_vals:
                    result.add_warning(f"Account {account_id}: '{col}' has unexpected value '{val}'")
        
        # Validate numeric columns
        for col, (min_val, max_val) in NUMERIC_RANGES.items():
            if col in df.columns:
                try:
                    val = float(row[col]) if pd.notna(row[col]) else 0
                    if val < min_val or val > max_val:
                        result.add_warning(f"Account {account_id}: '{col}' value {val} outside expected range [{min_val}, {max_val}]")
                except (ValueError, TypeError):
                    result.add_error(f"Account {account_id}: '{col}' is not a valid number")
        
        # Cross-field validations
        _validate_business_rules(row, account_id, result)
    
    result.validated_data = df.head(max_rows)
    return result


def _validate_business_rules(row: pd.Series, account_id: str, result: ValidationResult):
    """Validate business rules and data consistency"""
    
    try:
        dpd = int(row.get('dpd', 0)) if pd.notna(row.get('dpd')) else 0
        stage = str(row.get('delinquency_stage', 'SMA-0')).strip()
        
        # DPD should match delinquency stage
        expected_stage = _get_expected_stage(dpd)
        if stage != expected_stage:
            result.add_warning(
                f"Account {account_id}: DPD {dpd} suggests stage '{expected_stage}' but found '{stage}'"
            )
        
        # Outstanding shouldn't exceed loan amount (usually)
        loan_amount = float(row.get('loan_amount', 0)) if pd.notna(row.get('loan_amount')) else 0
        outstanding = float(row.get('outstanding_amount', 0)) if pd.notna(row.get('outstanding_amount')) else 0
        
        if outstanding > loan_amount * 1.5:  # Allow some interest accrual
            result.add_warning(
                f"Account {account_id}: Outstanding (₹{outstanding:,.0f}) significantly exceeds loan amount (₹{loan_amount:,.0f})"
            )
        
        # SARFAESI stage progression check
        sarfaesi = str(row.get('sarfaesi_stage', 'None')).strip()
        if sarfaesi != "None" and stage != "NPA":
            result.add_warning(
                f"Account {account_id}: SARFAESI stage '{sarfaesi}' but account is not NPA"
            )
        
        # Fraud flag special handling
        fraud = str(row.get('fraud_flag', 'No')).strip()
        if fraud == "Yes":
            result.add_warning(
                f"Account {account_id}: Fraud flag is set - special handling may be required"
            )
    
    except Exception as e:
        result.add_warning(f"Account {account_id}: Business rule validation error - {str(e)}")


def _get_expected_stage(dpd: int) -> str:
    """Get expected delinquency stage based on DPD"""
    if dpd <= 30:
        return "SMA-0"
    elif dpd <= 60:
        return "SMA-1"
    elif dpd <= 90:
        return "SMA-2"
    else:
        return "NPA"


def dataframe_to_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Convert DataFrame to list of dictionaries for processing"""
    records = []
    
    for idx, row in df.iterrows():
        record = {}
        for col in df.columns:
            val = row[col]
            # Handle NaN values
            if pd.isna(val):
                if col in NUMERIC_RANGES:
                    record[col] = 0
                else:
                    record[col] = ""
            else:
                record[col] = val
        records.append(record)
    
    return records
