import streamlit as st
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

st.sidebar.title("💎 Crown Threads ERP")
page = st.sidebar.radio("મેનુ પસંદ કરો", ["📤 Dispatch Scan", "📊 Dashboard & Audit"])

# --- PAGE 1: DISPATCH SCAN (કેમેરા સ્કેનર સાથે) ---
if page == "📤 Dispatch Scan":
    st.title("📤 Dispatch Scanning")
    
    # ફોનનો કેમેરો ઓપન કરવા માટે
    st.subheader("📸 Scan Barcode")
    img_file = st.camera_input("પાર્સલનો બારકોડ દેખાય તેમ ફોટો પાડો")
    
    awb_input = st.text_input("અથવા Order ID અહીં ટાઈપ કરો", key="barcode_manual")
    
    if awb_input:
        sheet1 = spreadsheet.worksheet("Sheet1")
        # Duplicate Check
        existing_data = pd.DataFrame(sheet1.get_all_records())
        if not existing_data.empty and str(awb_input) in existing_data['AWB'].astype(str).values:
            st.error(f"🚨 ઓર્ડર {awb_input} પહેલાથી સ્કેન થયેલો છે!")
        else:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ Confirm Dispatch", use_container_width=True):
                    sheet1.append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), awb_input, "Phone", "Dispatched"])
                    st.success("સેવ થઈ ગયું!")
                    st.rerun()
            with c2:
                if st.button("🚩 Soft Data Issue", use_container_width=True):
                    sheet1.append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), awb_input, "Phone", "Soft Data Issue"])
                    st.warning("સોફ્ટ ડેટામાં મુકાયું.")
                    st.rerun()

# --- PAGE 2: DASHBOARD & AUDIT ---
elif page == "📊 Dashboard & Audit":
    st.title("📊 Live Audit Dashboard")
    
    master_sheet = spreadsheet.worksheet("Ajio_Master_List")
    dispatch_sheet = spreadsheet.worksheet("Sheet1")
    
    # મોબાઈલમાં આ સેક્શન સીધું દેખાય તે માટે
    uploaded_file = st.file_uploader("Ajio Excel અપલોડ કરો", type=['xlsx'])
    if uploaded_file and st.button("ક્લાઉડમાં સેવ કરો", use_container_width=True):
        df_raw = pd.read_excel(uploaded_file, sheet_name='Order Details', header=None)
        header_row = next((i for i, row in df_raw.iterrows() if 'Customer Order Id' in row.values), None)
        ajio_df = pd.read_excel(uploaded_file, sheet_name='Order Details', skiprows=header_row)
        new_rows = [[datetime.now().strftime("%Y-%m-%d"), str(int(t)) if isinstance(t, float) else str(t), 'Pending'] for t in ajio_df['Customer Order Id'].dropna().unique()]
        master_sheet.append_rows(new_rows)
        st.success("ઓર્ડર સેવ થયા!")
        st.rerun()

    # ડેટા ટેબલ બતાવવા
    master_df = pd.DataFrame(master_sheet.get_all_records())
    user_df = pd.DataFrame(dispatch_sheet.get_all_records())
    
    if not master_df.empty:
        if not user_df.empty:
            latest_status = user_df.sort_values('Date').groupby('AWB').tail(1)
            status_dict = dict(zip(latest_status['AWB'].astype(str), latest_status['Status']))
        else: status_dict = {}

        master_df['Live_Status'] = master_df['Customer Order Id'].apply(lambda x: status_dict.get(str(x), '❌ Pending'))
        
        # આંકડા (Metrics)
        st.divider()
        st.metric("📦 કુલ બાકી", len(master_df[master_df['Live_Status'] == '❌ Pending']))
        st.metric("✅ ડિસ્પેચ થયેલા", len(master_df[master_df['Live_Status'] == 'Dispatched']))
        
        st.subheader("📋 ઓર્ડર લિસ્ટ")
        st.dataframe(master_df[['Customer Order Id', 'Live_Status']], use_container_width=True)
