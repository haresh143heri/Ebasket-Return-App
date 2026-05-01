import streamlit as st
import streamlit.components.v1 as components
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd

# ૧. Google Sheets કનેક્શન
@st.cache_resource
def connect_to_google():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("keys.json", scope)
        client = gspread.authorize(creds)
        return client.open("Crown_Threads_DB")
    except: return None

spreadsheet = connect_to_google()

st.set_page_config(page_title="Crown Threads ERP", layout="centered")
st.sidebar.title("💎 Crown Threads ERP")
page = st.sidebar.radio("મેનુ પસંદ કરો", ["📤 Dispatch Scan", "📊 Dashboard & Audit"])

if page == "📤 Dispatch Scan":
    st.title("📤 Live Barcode Scanner")
    
    # --- HTML5 QR Code Scanner (Back Camera & Auto Scan) ---
    # આ સેક્શન ફોનનો પાછળનો કેમેરો લાઈવ ખોલશે
    qr_code_html = """
    <div id="reader" style="width: 100%;"></div>
    <script src="https://unpkg.com/html5-qrcode"></script>
    <script>
        function onScanSuccess(decodedText, decodedResult) {
            // સ્કેન થયેલો કોડ સ્ટ્રીમલિટને મોકલો
            window.parent.postMessage({type: 'streamlit:set_widget_value', key: 'scanned_id', value: decodedText}, '*');
            // સ્કેન થયા પછી બીપ જેવો અવાજ અથવા એલર્ટ આપી શકાય
        }
        let html5QrcodeScanner = new Html5QrcodeScanner("reader", { fps: 10, qrbox: 250 });
        html5QrcodeScanner.render(onScanSuccess);
    </script>
    """
    components.html(qr_code_html, height=400)
    
    # સ્કેન થયેલો આઈડી અહીં દેખાશે
    scanned_id = st.text_input("સ્કેન થયેલ આઈડી:", key="scanned_id")
    
    if scanned_id:
        st.success(f"ઓર્ડર આઈડી મળી ગયો: {scanned_id}")
        sheet1 = spreadsheet.worksheet("Sheet1")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Confirm Dispatch", use_container_width=True):
                sheet1.append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), scanned_id, "Live Scan", "Dispatched"])
                st.toast("ડેટા સેવ થઈ ગયો!")
                st.rerun()
        with col2:
            if st.button("🚩 Soft Data Issue", use_container_width=True):
                sheet1.append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), scanned_id, "Live Scan", "Soft Data Issue"])
                st.warning("સોફ્ટ ડેટામાં મૂકાયું")
                st.rerun()

elif page == "📊 Dashboard & Audit":
    st.title("📊 Live Audit Dashboard")
    # (તમારો જૂનો ડેશબોર્ડ કોડ અહીં ચાલુ રહેશે)
    master_sheet = spreadsheet.worksheet("Ajio_Master_List")
    master_df = pd.DataFrame(master_sheet.get_all_records())
    if not master_df.empty:
        st.metric("📦 કુલ બાકી ઓર્ડર", len(master_df))
        st.dataframe(master_df, use_container_width=True)
