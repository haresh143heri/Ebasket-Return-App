import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import pandas as pd

# ૧. Google Sheets કનેક્શન સેટઅપ
@st.cache_resource
def connect_to_google():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("keys.json", scope)
        client = gspread.authorize(creds)
        return client.open("Crown_Threads_DB")
    except:
        return None

spreadsheet = connect_to_google()

# પેજ સેટઅપ
st.set_page_config(page_title="Crown Threads ERP", layout="wide")
st.sidebar.title("💎 Crown Threads ERP")
page = st.sidebar.radio("મેનુ પસંદ કરો", ["📤 Dispatch Scan", "📊 Dashboard & Audit"])

# --- PAGE 1: DISPATCH SCAN ---
if page == "📤 Dispatch Scan":
    st.title("📤 Dispatch Scanning")
    awb_input = st.text_input("Order ID સ્કેન કરો", placeholder="બારકોડ સ્કેનર વાપરો...")
    
    if awb_input:
        sheet1 = spreadsheet.worksheet("Sheet1")
        user_df = pd.DataFrame(sheet1.get_all_records())
        
        # Duplicate Check
        if not user_df.empty and str(awb_input) in user_df['AWB'].astype(str).values:
            st.error(f"🚨 RED ALERT: ઓર્ડર {awb_input} પહેલાથી સ્કેન થયેલો છે!")
        else:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ Confirm Dispatch"):
                    sheet1.append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), awb_input, "Auto", "Dispatched"])
                    st.success("સેવ થઈ ગયું!")
                    st.rerun()
            with c2:
                if st.button("🚩 Soft Data Issue"):
                    sheet1.append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), awb_input, "Auto", "Soft Data Issue"])
                    st.warning("સોફ્ટ ડેટામાં મુકાયું.")
                    st.rerun()

# --- PAGE 2: DASHBOARD & AUDIT ---
elif page == "📊 Dashboard & Audit":
    st.title("📊 Live Audit Dashboard")
    
    if spreadsheet:
        master_sheet = spreadsheet.worksheet("Ajio_Master_List")
        dispatch_sheet = spreadsheet.worksheet("Sheet1")
        
        master_df = pd.DataFrame(master_sheet.get_all_records())
        user_df = pd.DataFrame(dispatch_sheet.get_all_records())
        
        # ફાઇલ અપલોડ સેક્શન
        with st.expander("📁 સવારે નવી ફાઇલ અહીં અપલોડ કરો"):
            uploaded_file = st.file_uploader("Ajio Excel", type=['xlsx'])
            if uploaded_file and st.button("ક્લાઉડમાં ઓર્ડર સેવ કરો"):
                df_raw = pd.read_excel(uploaded_file, sheet_name='Order Details', header=None)
                header_row = next((i for i, row in df_raw.iterrows() if 'Customer Order Id' in row.values), None)
                ajio_df = pd.read_excel(uploaded_file, sheet_name='Order Details', skiprows=header_row)
                today_date = datetime.now().strftime("%Y-%m-%d")
                new_rows = [[today_date, str(int(t)) if isinstance(t, float) else str(t), 'Pending'] for t in ajio_df['Customer Order Id'].dropna().unique()]
                master_sheet.append_rows(new_rows)
                st.success("ઓર્ડર સેવ થયા!")
                st.rerun()

        if not master_df.empty:
            # સ્ટેટસ નક્કી કરવું
            if not user_df.empty:
                latest_status = user_df.sort_values('Date').groupby('AWB').tail(1)
                status_dict = dict(zip(latest_status['AWB'].astype(str), latest_status['Status']))
            else:
                status_dict = {}

            master_df['Live_Status'] = master_df['Customer Order Id'].apply(lambda x: status_dict.get(str(x), '❌ Pending'))

            # ફિલ્ટરિંગ
            pending_df = master_df[master_df['Live_Status'] == '❌ Pending']
            dispatched_df = master_df[master_df['Live_Status'] == 'Dispatched']
            soft_data_df = master_df[master_df['Live_Status'] == 'Soft Data Issue']

            # Metrics
            st.divider()
            col1, col2, col3 = st.columns(3)
            col1.metric("📦 કુલ બાકી", len(pending_df))
            col2.metric("✅ ડિસ્પેચ થયેલા", len(dispatched_df))
            col3.metric("🚩 સોફ્ટ ડેટા ઈશ્યુ", len(soft_data_df))
            st.divider()

            # Tables
            tab1, tab2, tab3 = st.tabs(["❌ Pending List", "🚩 Soft Data List", "✅ Dispatched List"])
            with tab1:
                st.dataframe(pending_df[['Upload_Date', 'Customer Order Id', 'Live_Status']], use_container_width=True)
            with tab2:
                st.dataframe(soft_data_df[['Upload_Date', 'Customer Order Id', 'Live_Status']], use_container_width=True)
            with tab3:
                st.dataframe(dispatched_df[['Upload_Date', 'Customer Order Id', 'Live_Status']], use_container_width=True)
