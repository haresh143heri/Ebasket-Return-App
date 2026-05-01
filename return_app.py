import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd

# ૧. Google Sheets કનેક્શન સેટઅપ
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

st.sidebar.title("💎 Crown Threads ERP")
page = st.sidebar.radio("મેનુ પસંદ કરો", ["📤 Dispatch Scan", "📊 Dashboard & Audit"])

# --- PAGE 1: DISPATCH SCAN ---
if page == "📤 Dispatch Scan":
    st.title("📤 Dispatch Scanning")
    
    # કેમેરા ઇનપુટ - મોબાઈલ માટે
    img_file = st.camera_input("📸 બારકોડ સ્કેન કરવા માટે ફોટો પાડો")
    
    # મેન્યુઅલ અથવા કીબોર્ડ સ્કેનર માટે બોક્સ
    awb_input = st.text_input("ઓર્ડર આઈડી અહીં લખો અથવા સ્કેન કરો", key="barcode_text")
    
    if awb_input:
        sheet1 = spreadsheet.worksheet("Sheet1")
        # સ્કેન કરેલ ડેટા સેવ કરવો
        if st.button("✅ Confirm Dispatch", use_container_width=True):
            sheet1.append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), awb_input, "Auto", "Dispatched"])
            st.success(f"{awb_input} સેવ થઈ ગયું!")
            st.rerun()

# --- PAGE 2: DASHBOARD & AUDIT ---
elif page == "📊 Dashboard & Audit":
    st.title("📊 Live Audit Dashboard")
    
    if spreadsheet:
        master_sheet = spreadsheet.worksheet("Ajio_Master_List")
        dispatch_sheet = spreadsheet.worksheet("Sheet1")
        
        # અપલોડ સેક્શન - હંમેશા ખુલ્લું રહેશે
        st.subheader("📁 નવી એક્સસેલ ફાઈલ અપલોડ કરો")
        uploaded_file = st.file_uploader("Ajio Excel પસંદ કરો", type=['xlsx'])
        
        if uploaded_file and st.button("🚀 ક્લાઉડમાં સેવ કરો", use_container_width=True):
            # ડેટા રીડ કરવો
            df_raw = pd.read_excel(uploaded_file, sheet_name='Order Details', header=None)
            header_row = next((i for i, row in df_raw.iterrows() if 'Customer Order Id' in row.values), None)
            ajio_df = pd.read_excel(uploaded_file, sheet_name='Order Details', skiprows=header_row)
            
            new_rows = [[datetime.now().strftime("%Y-%m-%d"), str(int(t)) if isinstance(t, float) else str(t), 'Pending'] for t in ajio_df['Customer Order Id'].dropna().unique()]
            master_sheet.append_rows(new_rows)
            st.success("ડેટા સફળતાપૂર્વક અપલોડ થયો!")
            st.rerun()

        # ડેટા ડિસ્પ્લે
        master_df = pd.DataFrame(master_sheet.get_all_records())
        user_df = pd.DataFrame(dispatch_sheet.get_all_records())

        if not master_df.empty:
            # લાઈવ સ્ટેટસ ચેક
            latest_status = user_df.sort_values('Date').groupby('AWB').tail(1) if not user_df.empty else pd.DataFrame()
            status_dict = dict(zip(latest_status['AWB'].astype(str), latest_status['Status'])) if not latest_status.empty else {}
            
            master_df['Live_Status'] = master_df['Customer Order Id'].apply(lambda x: status_dict.get(str(x), '❌ Pending'))

            # આંકડા
            pending = master_df[master_df['Live_Status'] == '❌ Pending']
            done = master_df[master_df['Live_Status'] == 'Dispatched']
            
            c1, c2 = st.columns(2)
            c1.metric("📦 પેન્ડિંગ", len(pending))
            c2.metric("✅ પૂર્ણ", len(done))
            
            st.dataframe(master_df[['Customer Order Id', 'Live_Status']], use_container_width=True)
        else:
            st.warning("⚠️ હજુ કોઈ ડેટા નથી. પ્લીઝ ઉપરથી એક્સસેલ ફાઈલ અપલોડ કરો.")
