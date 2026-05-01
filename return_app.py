import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd
import streamlit.components.v1 as components

# ૧. Google Sheets કનેક્શન
@st.cache_resource
def connect_to_google():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("keys.json", scope)
        client = gspread.authorize(creds)
        return client.open("Crown_Threads_DB")
    except Exception as e:
        st.error(f"કનેક્શનમાં ભૂલ: {e}")
        return None

spreadsheet = connect_to_google()

st.set_page_config(page_title="Crown Threads ERP", layout="centered")
st.sidebar.title("💎 Crown Threads ERP")
page = st.sidebar.radio("મેનુ પસંદ કરો", ["📤 Dispatch Scan", "📊 Dashboard & Audit"])

# --- PAGE 1: DISPATCH SCAN ---
if page == "📤 Dispatch Scan":
    st.title("📤 Live Back-Camera Scanner")
    
    # લાઈવ સ્કેનર (ફોટો પાડ્યા વગર સીધું સ્કેન થશે)
    # સ્કેન થયા પછી ID આપોઆપ બોક્સમાં આવી જશે
    qr_code_html = """
    <div id="reader" style="width: 100%; border-radius: 10px; overflow: hidden;"></div>
    <script src="https://unpkg.com/html5-qrcode"></script>
    <script>
        function onScanSuccess(decodedText, decodedResult) {
            // સ્કેન થયેલ ID ને ઇનપુટ બોક્સમાં મોકલો
            const input = window.parent.document.querySelector('input[aria-label="સ્કેન થયેલ ID અહીં દેખાશે:"]');
            if (input) {
                input.value = decodedText;
                input.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }
        let html5QrcodeScanner = new Html5QrcodeScanner("reader", { fps: 20, qrbox: 250 });
        html5QrcodeScanner.render(onScanSuccess);
    </script>
    """
    components.html(qr_code_html, height=350)
    
    # આ બોક્સમાં ID દેખાશે
    scanned_id = st.text_input("સ્કેન થયેલ ID અહીં દેખાશે:", key="main_scanner")
    
    if scanned_id:
        st.success(f"ID મળ્યો: {scanned_id}")
        sheet1 = spreadsheet.worksheet("Sheet1")
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Confirm Dispatch", use_container_width=True):
                sheet1.append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), scanned_id, "Live", "Dispatched"])
                st.balloons()
                st.rerun()
        with c2:
            if st.button("🚩 Soft Data Issue", use_container_width=True):
                sheet1.append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), scanned_id, "Live", "Soft Data Issue"])
                st.warning("સોફ્ટ ડેટા સેવ થયો")
                st.rerun()

# --- PAGE 2: DASHBOARD & AUDIT ---
elif page == "📊 Dashboard & Audit":
    st.title("📊 Live Audit")
    
    master_sheet = spreadsheet.worksheet("Ajio_Master_List")
    dispatch_sheet = spreadsheet.worksheet("Sheet1")
    
    # ફાઈલ અપલોડ (મોબાઈલમાં સીધું દેખાય તે માટે)
    with st.expander("📁 નવી ફાઈલ અપલોડ કરો", expanded=False):
        uploaded_file = st.file_uploader("Ajio Excel", type=['xlsx'])
        if uploaded_file and st.button("ક્લાઉડમાં સેવ કરો"):
            df_raw = pd.read_excel(uploaded_file, sheet_name='Order Details', header=None)
            header_row = next((i for i, row in df_raw.iterrows() if 'Customer Order Id' in row.values), None)
            ajio_df = pd.read_excel(uploaded_file, sheet_name='Order Details', skiprows=header_row)
            new_rows = [[datetime.now().strftime("%Y-%m-%d"), str(t), 'Pending'] for t in ajio_df['Customer Order Id'].dropna().unique()]
            master_sheet.append_rows(new_rows)
            st.success("સેવ થઈ ગયું!")
            st.rerun()

    # ડેટા ટેબલ અને મેટ્રિક્સ
    m_data = master_sheet.get_all_records()
    d_data = dispatch_sheet.get_all_records()
    
    master_df = pd.DataFrame(m_data) if m_data else pd.DataFrame(columns=['Upload_Date', 'Customer Order Id'])
    user_df = pd.DataFrame(d_data) if d_data else pd.DataFrame(columns=['AWB', 'Status'])
    
    if not master_df.empty:
        status_dict = dict(zip(user_df['AWB'].astype(str), user_df['Status'])) if not user_df.empty else {}
        master_df['Live_Status'] = master_df['Customer Order Id'].astype(str).apply(lambda x: status_dict.get(x, '❌ Pending'))
        
        # આંકડા
        pending_count = len(master_df[master_df['Live_Status'] == '❌ Pending'])
        done_count = len(master_df[master_df['Live_Status'] == 'Dispatched'])
        
        col1, col2 = st.columns(2)
        col1.metric("📦 બાકી", pending_count)
        col2.metric("✅ પૂર્ણ", done_count)
        
        # લિસ્ટ
        st.subheader("ઓર્ડર વિગત")
        st.dataframe(master_df[['Customer Order Id', 'Live_Status']], use_container_width=True)
