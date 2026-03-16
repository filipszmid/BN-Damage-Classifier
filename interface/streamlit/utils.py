import pandas as pd
from interface.streamlit.constants import B24_SCHEMA, SAP_SCHEMA, MAP_SCHEMA

def validate_excel(file, file_type):
    """Basic validation for the uploaded excel file to ensure schemas match exactly what we need."""
    try:
        xls = pd.ExcelFile(file)
        
        if file_type == 'b24':
            missing_tabs = []
            for tab in B24_SCHEMA.keys():
                if tab not in xls.sheet_names:
                    missing_tabs.append(tab)
            if missing_tabs:
                return False, f"Missing required tabs in B24 Report: {', '.join(missing_tabs)}"
                
            for tab, required_cols in B24_SCHEMA.items():
                df = pd.read_excel(xls, sheet_name=tab)
                missing_cols = [col for col in required_cols if col not in df.columns]
                
                if tab == 'Karty z czynnikiem chłodniczy' and 'part no.' in missing_cols:
                    if 'komponent' in df.columns:
                        missing_cols.remove('part no.')
                        
                if missing_cols:
                    return False, f"Missing required columns in tab '{tab}': {', '.join(missing_cols)}"
                    
        elif file_type == 'sap':
            df = pd.read_excel(xls)
            missing_cols = [col for col in SAP_SCHEMA['Required Columns'] if col not in df.columns]
            if missing_cols:
                return False, f"Missing required columns in SAP Report: {', '.join(missing_cols)}"
                
        elif file_type == 'map':
            df = pd.read_excel(xls)
            missing_cols = [col for col in MAP_SCHEMA['Required Columns'] if col not in df.columns]
            if missing_cols:
                return False, f"Missing required columns in Mapping File: {', '.join(missing_cols)}"
                
        return True, "Valid"
    except Exception as e:
        return False, f"Could not read the file correctly. Error: {str(e)}"
