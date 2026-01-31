import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import extra_streamlit_components as stx
import time

# --- 1. Setup & Auth ---
SHEET_NAME = "Ebasket_Database"
CREDS_FILE = "credentials.json"

def get_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        # Local Run
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, scope)
        client = gspread.authorize(creds)
        return client.open(SHEET_NAME)
    except:
        # Cloud Run
        try:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            return client.open(SHEET_NAME)
        except Exception as e:
            st.error("Connection Error: Secrets બરાબર સેટ નથી. Settings માં જઈને Secrets ઠીક કરો.")
            st.stop()

# --- 2. Database Functions ---
def save_to_sheet(df, tab_name):
    sh = get_connection()
    worksheet = sh.worksheet(tab_name)
    data = df.astype(str).values.tolist()
    if not worksheet.get_all_values():
        header = df.columns.tolist()
        worksheet.append_row(header)
    worksheet.append_rows(data)

def load_from_sheet(tab_name):
    sh = get_connection()
    worksheet = sh.worksheet(tab_name)
    data = worksheet.get_all_records()
    if not data: return pd.DataFrame()
    return pd.DataFrame(data)

def delete_by_date_sheet(tab_name, date_str):
    df = load_from_sheet(tab_name)
    if not df.empty and 'Upload_Date' in df.columns:
        df['Upload_Date'] = df['Upload_Date'].astype(str)
        new_df = df[df['Upload_Date'] != str(date_str)]
        sh = get_connection()
        worksheet = sh.worksheet(tab_name)
        worksheet.clear()
        if not new_df.empty:
            worksheet.update([new_df.columns.values.tolist()] + new_df.values.tolist())
        st.success(f"Deleted data for {date_str}")
    else:
        st.warning("No data found.")

# --- 3. Page Config & Login ---
st.set_page_config(page_title="Ebasket Cloud Dashboard", layout="wide")

def get_manager(): return stx.CookieManager()
cookie_manager = get_manager()

ADMIN_USER = "kushal@gmail.com"
ADMIN_PASS = "AdminKushal@721"

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

# Cookie Check
if not st.session_state['logged_in']:
    try:
        if cookie_manager.get(cookie="ebasket_auth_token") == "verified_user":
            st.session_state['logged_in'] = True
    except: pass

# Login Form
if not st.session_state['logged_in']:
    st.title("🔒 Ebasket Cloud Login")
    with st.form("login"):
        u = st.text_input("Email")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            if u == ADMIN_USER and p == ADMIN_PASS:
                cookie_manager.set("ebasket_auth_token", "verified_user")
                st.session_state['logged_in'] = True
                st.rerun()
            else: st.error("Invalid Credentials")
    st.stop()

# --- 4. Main App ---
st.sidebar.title("🚀 Ebasket Cloud Panel")
if st.sidebar.button("Logout"):
    cookie_manager.delete("ebasket_auth_token")
    st.session_state['logged_in'] = False
    st.rerun()

st.sidebar.header("📁 Add New Data")
s_files = st.sidebar.file_uploader("Scan Files", accept_multiple_files=True)
r_files = st.sidebar.file_uploader("RTV Files", accept_multiple_files=True)
o_files = st.sidebar.file_uploader("Order Files", accept_multiple_files=True)

def process(files, is_order=False):
    dfs = []
    current_date = datetime.now().strftime('%Y-%m-%d')
    for f in files:
        if f.name.endswith('.csv'): df = pd.read_csv(f, header=1 if is_order else 0)
        else: df = pd.read_excel(f, header=1 if is_order else 0)
        
        if is_order and 'Seller SKU ID' not in df.columns:
            f.seek(0)
            if f.name.endswith('.csv'): df = pd.read_csv(f)
            else: df = pd.read_excel(f)
        
        df['Upload_Date'] = current_date
        df['Source_File'] = f.name
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

if st.sidebar.button("☁️ Save to Google Sheet"):
    if s_files: save_to_sheet(process(s_files), 'scans')
    if r_files: save_to_sheet(process(r_files), 'rtv')
    if o_files: save_to_sheet(process(o_files, True), 'orders')
    if s_files or r_files or o_files:
        st.success("Data Saved!")
        st.cache_data.clear()
        st.rerun()

# --- 5. Data Loading & Empty State Handling ---
@st.cache_data(ttl=60)
def load_all_data():
    return load_from_sheet('scans'), load_from_sheet('rtv'), load_from_sheet('orders')

try:
    scans, rtvs, orders = load_all_data()
except:
    st.error("Connection Failed. Secrets Check કરો.")
    st.stop()

scan_set = set(scans.iloc[:,0].astype(str).str.strip()) if not scans.empty else set()

# Initialize Columns even if empty (Fixes KeyError)
if orders.empty:
    orders = pd.DataFrame(columns=['Open Order Date', 'Seller SKU ID', 'Article Name', 'Date', 'Upload_Date'])
else:
    orders['Date'] = pd.to_datetime(orders['Open Order Date'], dayfirst=True, errors='coerce')

if rtvs.empty:
    rtv_all = pd.DataFrame(columns=['Return AWB No', 'Cust Order No', 'RETURN ORDER NUMBER', 'Return Created Date', 'Status', 'Date', 'Category', 'SELLER SKU', 'Upload_Date'])
else:
    rtvs['Return AWB No'] = rtvs['Return AWB No'].astype(str).str.strip()
    rtvs['Cust Order No'] = rtvs['Cust Order No'].astype(str).str.strip()
    rtvs['RETURN ORDER NUMBER'] = rtvs['RETURN ORDER NUMBER'].astype(str).str.strip()
    
    rtvs['Status'] = rtvs.apply(lambda r: 'Matched' if any(str(r.get(c,'')).strip() in scan_set for c in ['Return AWB No','Cust Order No','RETURN ORDER NUMBER'] if str(r.get(c,'')) != 'nan') else 'Missing', axis=1)
    rtvs['Date'] = pd.to_datetime(rtvs['Return Created Date'].astype(str).str.replace(' IST',''), errors='coerce')
    
    pm = orders[['Seller SKU ID', 'Article Name']].drop_duplicates().rename(columns={'Seller SKU ID':'SELLER SKU'}) if not orders.empty else pd.DataFrame(columns=['SELLER SKU', 'Article Name'])
    rtv_all = pd.merge(rtvs, pm, on='SELLER SKU', how='left')
    
    def get_cat(name):
        n = str(name).lower()
        if 'saree' in n: return 'Saree'
        elif 'shirt' in n: return 'Shirt/T-Shirt'
        elif 'kurta' in n: return 'Kurta Set'
        return 'Other'
    
    rtv_all['Category'] = rtv_all['Article Name'].apply(get_cat)

# --- TABS ---
t_daily, t1, t2, t3, t4, t5 = st.tabs(["📅 Daily", "📆 Monthly", "📊 Category", "🚨 Missing", "📦 SKU", "🗂️ Manage"])

with t_daily:
    st.header("Daily Report")
    sel_date = st.date_input("Select Date", datetime.now())
    
    # Safe Filtering
    d_orders = orders[orders['Date'].dt.date == sel_date] if not orders.empty else pd.DataFrame()
    d_returns = rtv_all[rtv_all['Date'].dt.date == sel_date] if not rtv_all.empty else pd.DataFrame(columns=['Status', 'Category'])
    
    # Check if 'Status' column exists before accessing
    if 'Status' in d_returns.columns:
        d_missing = d_returns[d_returns['Status'] == 'Missing']
    else:
        d_missing = pd.DataFrame()

    c1, c2, c3 = st.columns(3)
    c1.metric("Orders", len(d_orders))
    c2.metric("Returns", len(d_returns))
    c3.metric("Missing", len(d_missing))
    
    if not d_missing.empty:
        st.dataframe(d_missing, use_container_width=True)

with t5:
    st.header("Manage Data")
    tab = st.selectbox("Select Tab", ["scans", "rtv", "orders"])
    if st.button("Refresh"): st.cache_data.clear(); st.rerun()
    date_d = st.text_input("Date (YYYY-MM-DD)")
    if st.button("Delete"):
        delete_by_date_sheet(tab, date_d)
        st.cache_data.clear()
        st.rerun()

# (બાકીના ટૅબ્સ જેમ છે તેમ રાખો અથવા આ જ લોજિકથી ભરો)
