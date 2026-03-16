import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.comparsion.pipeline import ComparisonPipeline
from interface.streamlit.constants import B24_SCHEMA, SAP_SCHEMA, MAP_SCHEMA
from interface.streamlit.utils import validate_excel
from src.router import get_db_client, process_report, save_label_to_db, delete_label_from_db
from src.schema import LabelInfo
import asyncio

load_dotenv()
EXPECTED_USER = os.getenv("USER", "admin")
EXPECTED_PASSWORD = os.getenv("PASSWORD", "password")

st.set_page_config(
    page_title="Excel Comparison Mod",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    /* Clean Toolbar and Deploy Buttons */
    .reportview-container { margin-top: -2em; }
    #MainMenu {visibility: hidden;}
    .stDeployButton {display:none;}
    .stAppDeployButton {display:none;}
    footer {visibility: hidden;}
    #stDecoration {display:none;}
    
    /* Elegant Title Font */
    h1 {
        font-family: 'Inter', sans-serif;
        font-weight: 800 !important;
        font-size: 2.5rem !important;
        margin-bottom: 0px !important;
        padding-bottom: 0px !important;
    }
    
    /* Primary buttons */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        background: linear-gradient(135deg, #3b82f6, #2563eb);
        color: white;
        border: none;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #2563eb, #1d4ed8);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        color: white;
    }
</style>
""", unsafe_allow_html=True)

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if 'language' not in st.session_state:
    st.session_state['language'] = 'POL'

def t(en_text: str, pl_text: str) -> str:
    """Helper function to translate text based on the current session state language."""
    return pl_text if st.session_state.get('language', 'ENG') == 'POL' else en_text

def login():
    st.markdown(f"<h1 style='text-align: center;'>{t('B24 vs SAP Comparison', 'Porównanie B24 vs SAP')}</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center; color: #64748b;'>{t('Please authenticate to continue.', 'Zaloguj się, aby kontynuować.')}</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input(t("Username", "Nazwa użytkownika"), placeholder=t("Enter your username", "Wpisz nazwę użytkownika"))
            password = st.text_input(t("Password", "Hasło"), type="password", placeholder=t("Enter your password", "Wpisz hasło"))
            submit_button = st.form_submit_button(t("Sign In", "Zaloguj"))
            
            if submit_button:
                if username == EXPECTED_USER and password == EXPECTED_PASSWORD:
                    st.session_state['logged_in'] = True
                    st.rerun()
                else:
                    st.error(t("Invalid username or password.", "Nieprawidłowa nazwa użytkownika lub hasło."))

def save_uploaded_file(uploaded_file, destination):
    with open(destination, "wb") as f:
        f.write(uploaded_file.getbuffer())

def preview_dataframe(file):
    """Safely loads a few rows of an excel file for preview."""
    try:
        df = pd.read_excel(file, nrows=3)
        st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.caption("Preview not available")

def render_help():
    st.markdown("<h1>📚 Help & Documentation</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    # Resolving path to src/comparsion/README.md
    readme_path = Path(__file__).parent.parent.parent / "src" / "comparsion" / "README.md"
    if readme_path.exists():
        with open(readme_path, "r", encoding="utf-8") as f:
            st.markdown(f.read())
    else:
        st.error(f"Could not find the documentation file at: {readme_path}")

def render_settings():
    st.markdown("<h1>System Settings & Schemas</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #64748b; font-size: 1.1em;'>Below are the expected data schemas for the Comparison process. If the uploaded files do not match these exactly, the validation step will fail.</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("B24 Report Schema")
        st.caption("Expected Tabs and their Required Columns")
        st.json(B24_SCHEMA)
        
    with col2:
        st.subheader("SAP Report Schema")
        st.caption("Required Columns on the first sheet")
        st.json(SAP_SCHEMA)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        st.subheader("Mapping Dictionary Schema")
        st.caption("Required Columns on the first sheet")
        st.json(MAP_SCHEMA)

def render_comparison():
    DATA_DIR = Path("data/comparsion")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    col_title, col_btn_run, col_btn_clear = st.columns([4, 1, 1])
    
    with col_title:
        st.markdown(f"<h1>{t('B24 vs SAP Parts Comparison', 'Porównanie Części B24 vs SAP')}</h1>", unsafe_allow_html=True)

    with col_btn_run:
        # Adding some top margin to align with h1
        st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
        can_run = all(st.session_state.get(k) is not None for k in ["b24", "sap", "map"])
        run_clicked = st.button(t("Run Comparison", "Uruchom porównanie"), use_container_width=True, disabled=not can_run)
        
    with col_btn_clear:
        st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
        clear_clicked = st.button(t("Clear", "Wyczyść"), use_container_width=True)
        
    st.markdown(f"<p style='color: #64748b; font-size: 1.1em; margin-top: 5px;'>{t('Upload your reports below to generate a detailed comparison.', 'Prześlij swoje raporty poniżej, aby wygenerować szczegółowe porównanie.')}</p>", unsafe_allow_html=True)
    st.markdown("---")

    if clear_clicked:
        for key in ["b24", "sap", "map"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

    colA, colB, colC = st.columns(3)
    
    with colA:
        st.subheader(t("1. B24 Report", "1. Raport B24"))
        b24_file = st.file_uploader(t("Upload B24 Report", "Wgraj Raport B24"), type=["xlsx", "xls"], key="b24")
        with st.expander(t("ℹ️ What is this file?", "ℹ️ Co to za plik?"), expanded=False):
            st.markdown(t("This is the raw parts usage report exported directly from the **B24** system. It contains the raw parts, refrigerants, and statuses.", "Jest to surowy raport zużycia części wyeksportowany z systemu **B24**. Zawiera surowe informacje o częściach, czynnikach chłodniczych oraz statusach."))
            st.markdown(t("**Required Tabs:**\n", "**Wymagane zakładki:**\n") + "\n".join([f"- `{t}`" for t in B24_SCHEMA.keys()]))
        if b24_file:
            st.markdown(t("**Preview:**", "**Podgląd:**"))
            preview_dataframe(b24_file)
    
    with colB:
        st.subheader(t("2. SAP Report", "2. Raport SAP"))
        sap_file = st.file_uploader(t("Upload SAP Report", "Wgraj Raport SAP"), type=["xlsx", "xls"], key="sap")
        with st.expander(t("ℹ️ What is this file?", "ℹ️ Co to za plik?"), expanded=False):
            st.markdown(t("This is the report generated by the **SAP** system, containing the final logged usage quantities that we need to compare B24 against.", "Jest to raport wygenerowany przez system **SAP**, zawierający docelowe ilości zużycia, z którymi porównujemy B24."))
            st.markdown(t("**Required Columns:**\n", "**Wymagane Kolumny:**\n") + "\n".join([f"- `{c}`" for c in SAP_SCHEMA['Required Columns']]))
        if sap_file:
            st.markdown(t("**Preview:**", "**Podgląd:**"))
            preview_dataframe(sap_file)
            
    with colC:
        st.subheader(t("3. Mapping Dictionary", "3. Słownik Mapowań"))
        map_file = st.file_uploader(t("Upload Index Mapping", "Wgraj Mapowanie Indeksów"), type=["xlsx", "xls"], key="map")
        with st.expander(t("ℹ️ What is this file?", "ℹ️ Co to za plik?"), expanded=False):
            st.markdown(t("This is your reference excel. It bridges the gap between B24 parts strings and SAP Index codes, enabling the system to link them together properly.", "Arkusz referencyjny. Stanowi pomost między tekstami części w B24 a kodami indeksów w SAP, umożliwiając poprawne powiązanie."))
            st.markdown(t("**Required Columns:**\n", "**Wymagane Kolumny:**\n") + "\n".join([f"- `{c}`" for c in MAP_SCHEMA['Required Columns']]))
        if map_file:
            st.markdown(t("**Preview:**", "**Podgląd:**"))
            preview_dataframe(map_file)
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    if run_clicked:
        if not all([b24_file, sap_file, map_file]):
            st.warning(t("⚠️ Please upload all 3 required files before running.", "⚠️ Proszę wgrać wszystkie 3 wymagane pliki przed uruchomieniem."))
            return
            
        with st.status("Initializing Validation and Processing...", expanded=True) as status:
            st.write("Checking B24 Report schema...")
            is_valid, msg = validate_excel(b24_file, 'b24')
            if not is_valid:
                status.update(label="Validation Failed", state="error", expanded=True)
                st.error(f"B24 File Error: {msg}")
                return
                
            st.write("Checking SAP Report schema...")
            is_valid, msg = validate_excel(sap_file, 'sap')
            if not is_valid:
                status.update(label="Validation Failed", state="error", expanded=True)
                st.error(f"SAP File Error: {msg}")
                return
                
            st.write("Checking Mapping File schema...")
            is_valid, msg = validate_excel(map_file, 'map')
            if not is_valid:
                status.update(label="Validation Failed", state="error", expanded=True)
                st.error(f"Mapping File Error: {msg}")
                return
                
            st.write("Saving validated files securely to disk...")
            b24_path = DATA_DIR / "temp_b24.xlsx"
            sap_path = DATA_DIR / "temp_sap.xlsx"
            map_path = DATA_DIR / "temp_map.xlsx"
            out_path = DATA_DIR / "comparison_output.xlsx"
            
            save_uploaded_file(b24_file, b24_path)
            save_uploaded_file(sap_file, sap_path)
            save_uploaded_file(map_file, map_path)
            
            st.write("Running complex normalization and comparison algorithms...")
            try:
                pipeline = ComparisonPipeline(
                    b24_path=str(b24_path),
                    sap_path=str(sap_path),
                    map_path=str(map_path),
                    output_path=str(out_path)
                )
                pipeline.run()
                status.update(label="Analysis complete! Report generated successfully.", state="complete", expanded=False)
            except Exception as e:
                status.update(label="Process Failed", state="error", expanded=True)
                st.error(f"An error occurred during pipeline execution: {str(e)}")
                return
                
        st.balloons()
        st.success("🎉 Process finished successfully! You can download your detailed report below.")
        
        with open(out_path, "rb") as f:
            st.download_button(
                label="Download Comparison Result",
                data=f,
                file_name="comparison_output.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )

def main_app():
    if 'current_page' not in st.session_state:
        st.session_state['current_page'] = 'Excel Comparison'
        

def render_recommendation_card(title, rec_list):
    st.markdown(f"**{title}**")
    if not rec_list:
        st.caption(t("No recommendations found.", "Brak rekomendacji."))
        return
        
    def sort_key(x):
        loc = x.get('localisation') or x.get('location') or ""
        comp = x.get('component') or ""
        return (str(loc), str(comp))
        
    try:
        sorted_recs = sorted(rec_list, key=sort_key)
    except Exception:
        sorted_recs = rec_list
    
    for rec in sorted_recs:
        loc = rec.get('localisation') or rec.get('location') or "N/A"
        comp = rec.get('component') or "N/A"
        rep = rec.get('repair_type') or "N/A"
        dam = rec.get('damage') or "N/A"
        qty = rec.get('quantity')
        st.markdown(f"""
        <div style="padding: 10px; border-radius: 5px; margin-bottom: 5px; background-color: #1e293b; border-left: 4px solid #3b82f6; color: #f8fafc; font-size: 0.9em;">
            <strong>Location:</strong> {loc} | <strong>Component:</strong> {comp} <br>
            <strong>Repair:</strong> {rep} | <strong>Damage:</strong> {dam} | <strong>Qty:</strong> {qty}
        </div>
        """, unsafe_allow_html=True)

def render_classifier():
    col_title, col_btn_run = st.columns([5, 1])
    with col_title:
        st.markdown(f"<h1>{t('Inspection scanner', 'Skaner inspekcji')}</h1>", unsafe_allow_html=True)
    
    with col_btn_run:
        # Adding some top margin to align with h1
        st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
        run_clicked = st.button(t("Process report", "Przetwarzaj raport"), use_container_width=True, type="primary")

    st.markdown(f"<p style='color: #64748b; font-size: 1.1em;'>{t('Upload your `.webp` container inspection report and let the AI classify required repairs automatically.', 'Wgraj raport inspekcji kontenera `.webp`, a AI sklasyfikuje wymagane naprawy.')}</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader(t("Report Details", "Szczegóły raportu"))
        container_type = st.text_input(t("Container Type", "Typ kontenera"), value="dc", help="e.g. rf, dc")
        shipowner = st.text_input(t("Shipowner", "Armator"), value="cma", help="e.g. cma, msc")
        report_file = st.file_uploader(t("Upload Image Report (.webp)", "Wgraj raport ze zdjęciami (.webp)"), type=["webp"])
        
    if run_clicked:
        if not report_file:
            st.warning(t("Please upload a `.webp` report file first.", "Proszę najpierw wgrać plik raportu `.webp`."))
            return
        if not container_type or not shipowner:
            st.warning(t("Please provide container type and shipowner.", "Proszę podać typ kontenera i armatora."))
            return
            
        with st.status(t("Analyzing report...", "Analizowanie raportu..."), expanded=True) as status:
            st.write(t("Connecting to Database...", "Łączenie z Bazą Danych..."))
            try:
                client, db = asyncio.run(get_db_client())
            except Exception as e:
                status.update(label=t("Database Error", "Błąd Bazy Danych"), state="error", expanded=True)
                st.error(f"{t('Could not connect to database:', 'Nie można połączyć z bazą danych:')} {str(e)}")
                return
            
            st.write(t("Running OCR & Damage Classification Pipeline...", "Uruchamianie OCR i Klasyfikacji Uszkodzeń..."))
            try:
                file_bytes = report_file.getvalue()
                result = asyncio.run(process_report(
                    db=db,
                    container_type=container_type,
                    shipowner=shipowner,
                    filename=report_file.name,
                    file_bytes=file_bytes
                ))
                client.close()
                
                # Store result in session state to persist across reruns
                st.session_state['classifier_result'] = result
                st.session_state['classifier_success'] = True
                status.update(label=t("Analysis complete!", "Analiza zakończona!"), state="complete", expanded=False)
            except Exception as e:
                client.close()
                status.update(label=t("Process Failed", "Proces Nieudany"), state="error", expanded=True)
                st.error(f"{t('Pipeline Execution Failed:', 'Wykonanie Pipeline Nieudane:')} {str(e)}")
                return
    
    with col2:
        st.subheader(t("Results & Feedback", "Wyniki"))
        if 'classifier_success' not in st.session_state:
            st.info(t("Upload a report on the left and click 'Process Report' to see results.", "Wgraj raport po lewej i kliknij 'Przetwarzaj Raport', aby zobaczyć wyniki."))
        else:
            result = st.session_state['classifier_result']
            st.success(f"**{t('Pipeline ID', 'ID Przetwarzania')}**: `{result.get('pipeline_id')}`")
            st.caption(result.get("description", ""))
            
            # Display results in columns
            res_col1, res_col2 = st.columns(2)
            with res_col1:
                render_recommendation_card(t("LLM Recommendations (GPT)", "Rekomendacje LLM (GPT)"), result.get("recommendations", []))
                
            with res_col2:
                render_recommendation_card(t("Local Model Recommendations", "Rekomendacje Modelu Lokalnego"), result.get("local_model_recommendations", []))
                
            st.markdown("---")
            st.subheader(t("Submit Corrections (Feedback)", "Zgłoś Poprawki (Feedback)"))
            st.caption(t("Build a list of correct labels and submit them all at once.", "Zbuduj listę poprawnych etykiet i wyślij je wszystkie naraz."))
            
            if 'feedback_list' not in st.session_state:
                st.session_state['feedback_list'] = []
                
            # Form to add to list
            with st.form("add_feedback_form", clear_on_submit=True):
                st.markdown("### " + t("Add Label", "Dodaj etykietę"))
                fb_localisation = st.text_input(t("Localisation Code", "Kod Lokalizacji"))
                fb_component = st.text_input(t("Component (optional)", "Komponent (opcjonalnie)"))
                fb_repair_type = st.text_input(t("Repair Type (optional)", "Rodzaj Naprawy (opcjonalnie)"))
                fb_damage = st.text_input(t("Damage (optional)", "Uszkodzenie (opcjonalnie)"))
                
                fb_col1, fb_col2, fb_col3 = st.columns(3)
                with fb_col1:
                    fb_quantity = st.number_input(t("Quantity", "Ilość"), min_value=1, value=1)
                with fb_col2:
                    fb_length = st.number_input(t("Length", "Długość"), min_value=0.0, value=0.0)
                with fb_col3:
                    fb_width = st.number_input(t("Width", "Szerokość"), min_value=0.0, value=0.0)
                
                add_to_list = st.form_submit_button(t("➕ Add Label to List", "➕ Dodaj Etkietę Do Listy"), use_container_width=True)
            
            msg_placeholder = st.empty()
                
            if add_to_list:
                if not fb_localisation:
                    msg_placeholder.error(t("Localisation code is required!", "Kod lokalizacji jest wymagany!"))
                else:
                    new_item = {
                        "localisation": fb_localisation,
                        "component": fb_component,
                        "repair_type": fb_repair_type,
                        "damage": fb_damage,
                        "quantity": fb_quantity,
                        "length": fb_length,
                        "width": fb_width,
                        "hours": None,
                        "material": None,
                        "cost": None
                    }
                    st.session_state['feedback_list'] = st.session_state['feedback_list'] + [new_item]
                    msg_placeholder.success(f"{t('Added', 'Dodano')} {fb_localisation} {t('to pending labels.', 'do oczekujących powiązań.')}")
            
            st.markdown(f"**{t('Pending Labels:', 'Oczekujące Powiązania:')}**")
            if not st.session_state['feedback_list']:
                st.info(t("No labels added yet.", "Nie dodano jeszcze żadnych etykiet."))
            else:
                for i, lbl in enumerate(st.session_state['feedback_list']):
                    st.markdown(f"`{i+1}.` **{t('Location', 'Lokalizacja')}:** {lbl['localisation']} | **{t('Component', 'Komponent')}:** {lbl.get('component','')} | **{t('Qty', 'Ilość')}:** {lbl.get('quantity','')}")
            
            col_save, col_clear, col_del = st.columns(3)
            with col_save:
                if st.button(t("💾 Save All to DB", "💾 Zapisz Wszystko do bazy"), type="primary", use_container_width=True):
                    if not st.session_state['feedback_list']:
                        st.warning(t("No labels to save.", "Brak etykiet do zapisania."))
                    else:
                        try:
                            client, db = asyncio.run(get_db_client())
                            labels = [LabelInfo(**lbl) for lbl in st.session_state['feedback_list']]
                            resp = asyncio.run(save_label_to_db(db, result['pipeline_id'], labels))
                            client.close()
                            st.success(resp.get('message', t('Saved successfully!', 'Zapisano pomyślnie!')))
                            st.session_state['feedback_list'] = [] # Clear after save
                            st.rerun()
                        except Exception as e:
                            st.error(f"{t('Failed to save labels', 'Nie udało się zapisać etykiet')}: {e}")
            with col_clear:
                if st.button(t("🗑️ Clear List", "🗑️ Wyczyść Listę"), use_container_width=True):
                    st.session_state['feedback_list'] = []
                    st.rerun()
            with col_del:
                if st.button(t("🚨 Delete DB Labels", "🚨 Usuń Etykiety BD"), use_container_width=True):
                    try:
                        client, db = asyncio.run(get_db_client())
                        resp = asyncio.run(delete_label_from_db(db, result['pipeline_id']))
                        client.close()
                        st.success(resp.get('message', t('Deleted successfully!', 'Usunięto pomyślnie!')))
                    except Exception as e:
                        st.error(f"{t('Failed to delete label:', 'Nie udało się usunąć etykiet:')} {e}")

def main_app():
    if 'current_page' not in st.session_state:
        st.session_state['current_page'] = 'Excel Comparison'
        
    # Sidebar Navigation using Buttons instead of Radio
    with st.sidebar:
        st.title(t("Navigation", "Nawigacja"))
        st.markdown("<br>", unsafe_allow_html=True)

        if st.button(t("📊 Excel Comparison", "📊 Porównanie Excel"), use_container_width=True):
            st.session_state['current_page'] = 'Excel Comparison'

        if st.button(t("🤖 Report scanner", "🤖 Skaner raportów"), use_container_width=True):
            st.session_state['current_page'] = 'AI App'

        if st.button(t("⚙️ Settings", "⚙️ Ustawienia"), use_container_width=True):
            st.session_state['current_page'] = 'Settings'
            
        if st.button(t("❓ Help", "❓ Pomoc"), use_container_width=True):
            st.session_state['current_page'] = 'Help'
            
        st.markdown("<div style='height: 35vh;'></div>", unsafe_allow_html=True)
        
        lang_mode = st.session_state.get('language', 'ENG')
        btn_label = "🇵🇱 Przełącz na Polski" if lang_mode == "ENG" else "🇬🇧 Switch to English"
        
        # A slightly different aesthetic for the language toggle
        if st.button(btn_label, use_container_width=True, type="secondary"):
            st.session_state['language'] = "POL" if lang_mode == "ENG" else "ENG"
            st.rerun()
            
        st.markdown("<hr style='margin: 0.5em 0;'>", unsafe_allow_html=True)
        st.caption(t("Logged in as Admin", "Zalogowano jako Admin"))
        if st.button(t("Log out", "Wyloguj"), use_container_width=True):
            st.session_state['logged_in'] = False
            st.rerun()

    # Route to the appropriate page
    if st.session_state['current_page'] == 'AI App':
        render_classifier()
    elif st.session_state['current_page'] == 'Excel Comparison':
        render_comparison()
    elif st.session_state['current_page'] == 'Help':
        render_help()
    elif st.session_state['current_page'] == 'Settings':
        render_settings()

if __name__ == "__main__":
    if not st.session_state['logged_in']:
        login()
    else:
        main_app()
