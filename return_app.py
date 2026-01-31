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
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, scope)
        client = gspread.authorize(creds)
        return client.open(SHEET_NAME)
    except:
        try:
            if "gcp_service_account" in st.secrets:
                creds_dict = dict(st.secrets["gcp_service_account"])
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                client = gspread.authorize(creds)
                return client.open(SHEET_NAME)
            else:
                st.error("Secrets missing.")
                st.stop()
        except Exception as e:
            st.error(f"Connection Error: {e}")
            st.stop()

# --- 2. Database Functions ---
def save_to_sheet(df, tab_name):
    if df.empty: return
    sh = get_connection()
    try:
        worksheet = sh.worksheet(tab_name)
    except:
        worksheet = sh.add_worksheet(title=tab_name, rows="1000", cols="20")
        
    data = df.astype(str).values.tolist()
    
    # If sheet is empty, add header
    if not worksheet.get_all_values():
        header = df.columns.tolist()
        worksheet.append_row(header)
    
    worksheet.append_rows(data)

def load_from_sheet(tab_name):
    sh = get_connection()
    try:
        worksheet = sh.worksheet(tab_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

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
st.set_page_config(page_title="Ebasket Cloud Panel", layout="wide")

def get_manager(): return stx.CookieManager()
cookie_manager = get_manager()

ADMIN_USER = "kushal@gmail.com"
ADMIN_PASS = "AdminKushal@721"

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    try:
        if cookie_manager.get(cookie="ebasket_auth_token") == "verified_user":
            st.session_state['logged_in'] = True
    except: pass

if not st.session_state['logged_in']:
    st.title("🔒 Ebasket Cloud Login")
    with st.form("login_form"):
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

# --- SMART FILE PROCESSOR (Auto-Detect Header) ---
def smart_read(file, file_type):
    # Determine loader
    if file.name.endswith('.csv'):
        # Try reading normally first
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file)

    # 1. SCAN FILES: Just take the first column, no matter the name
    if file_type == 'scan':
        df = df.iloc[:, :1] # Keep only 1st column
        df.columns = ['Scanned_ID'] # Rename strictly
        return df

    # 2. RTV/ORDER FILES: Find the correct header row
    # Look for key columns to identify the header row
    keywords = ['Return AWB No', 'Seller SKU ID', 'Order ID', 'AWB Number', 'Forward AWB No', 'RETURN ORDER NUMBER']
    
    # Check if current header is correct
    if any(k in df.columns for k in keywords):
        return df
    
    # If not, search in first 10 rows
    file.seek(0) # Reset file pointer
    if file.name.endswith('.csv'):
        df_raw = pd.read_csv(file, header=None)
    else:
        df_raw = pd.read_excel(file, header=None)
        
    for i, row in df_raw.head(10).iterrows():
        # Convert row to string and check for keywords
        row_str = row.astype(str).str.strip().tolist()
        if any(k in row_str for k in keywords):
            # Found the header row at index 'i'
            file.seek(0)
            if file.name.endswith('.csv'):
                return pd.read_csv(file, header=i)
            else:
                return pd.read_excel(file, header=i)
    
    return df # Return original if nothing found

def process_files(files, f_type):
    dfs = []
    current_date = datetime.now().strftime('%Y-%m-%d')
    for f in files:
        try:
            df = smart_read(f, f_type)
            df['Upload_Date'] = current_date
            df['Source_File'] = f.name
            dfs.append(df)
        except Exception as e:
            st.error(f"Error reading {f.name}: {e}")
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

if st.sidebar.button("☁️ Save to Google Sheet"):
    with st.spinner("Processing & Saving..."):
        if s_files: save_to_sheet(process_files(s_files, 'scan'), 'scans')
        if r_files: save_to_sheet(process_files(r_files, 'rtv'), 'rtv')
        if o_files: save_to_sheet(process_files(o_files, 'order'), 'orders')
        
        if s_files or r_files or o_files:
            st.success("Data Saved Successfully!")
            st.cache_data.clear()
            time.sleep(1)
            st.rerun()
        else:
            st.warning("Select files first.")

# --- 5. Data Loading ---
@st.cache_data(ttl=60)
def load_all_data():
    return load_from_sheet('scans'), load_from_sheet('rtv'), load_from_sheet('orders')

try:
    scans, rtvs, orders = load_all_data()
except:
    st.error("Connection Failed. Check Secrets.")
    st.stop()

# --- Logic & Matching ---
# Prepare Scan Set (Always take 1st column of scans)
scan_set = set()
if not scans.empty:
    # Ensure we take the column named 'Scanned_ID' or the first column
    col_name = 'Scanned_ID' if 'Scanned_ID' in scans.columns else scans.columns[0]
    scan_set = set(scans[col_name].astype(str).str.strip())

# Orders Prep
if not orders.empty:
    # Try to find Date column
    date_col = next((c for c in orders.columns if 'Date' in c or 'Time' in c), None)
    if date_col:
        orders['Date'] = pd.to_datetime(orders[date_col], dayfirst=True, errors='coerce')
    else:
        orders['Date'] = pd.to_datetime([])

    # Try to find SKU and Article columns
    sku_col = next((c for c in orders.columns if 'SKU' in c), 'Seller SKU ID')
    art_col = next((c for c in orders.columns if 'Article' in c or 'Product' in c), 'Article Name')
    
    if sku_col in orders.columns and art_col in orders.columns:
        pm = orders[[sku_col, art_col]].drop_duplicates().rename(columns={sku_col:'SELLER SKU', art_col:'Article Name'})
    else:
        pm = pd.DataFrame(columns=['SELLER SKU', 'Article Name'])
else:
    orders = pd.DataFrame(columns=['Date'])
    pm = pd.DataFrame(columns=['SELLER SKU', 'Article Name'])

# RTV Prep & Matching
if not rtvs.empty:
    # Auto-detect relevant columns for RTV
    awb_col = next((c for c in rtvs.columns if 'AWB' in c and 'Return' in c), 'Return AWB No')
    cust_col = next((c for c in rtvs.columns if 'Cust' in c or 'Order No' in c), 'Cust Order No')
    ret_ord_col = next((c for c in rtvs.columns if 'RETURN' in c and 'ORDER' in c), 'RETURN ORDER NUMBER')
    sku_col_rtv = next((c for c in rtvs.columns if 'SKU' in c), 'Seller SKU ID')
    date_col_rtv = next((c for c in rtvs.columns if 'Date' in c and 'Created' in c), 'Return Created Date')

    # Status Matching Logic
    def check_match(row):
        # Check all possible columns against scan_set
        for col in [awb_col, cust_col, ret_ord_col]:
            if col in row.index:
                val = str(row[col]).strip()
                if val in scan_set:
                    return 'Matched'
        return 'Missing'

    rtvs['Status'] = rtvs.apply(check_match, axis=1)
    
    # Date Cleanup
    if date_col_rtv in rtvs.columns:
        rtvs['Date'] = pd.to_datetime(rtvs[date_col_rtv].astype(str).str.replace(' IST',''), errors='coerce')
    else:
        rtvs['Date'] = pd.to_datetime([])

    # Merge for Category
    if sku_col_rtv in rtvs.columns:
        rtvs = rtvs.rename(columns={sku_col_rtv: 'SELLER SKU'})
        rtv_all = pd.merge(rtvs, pm, on='SELLER SKU', how='left')
    else:
        rtv_all = rtvs
        rtv_all['Article Name'] = 'Unknown'

    # Category Helper
    def get_cat(name):
        n = str(name).lower()
        if 'saree' in n: return 'Saree'
        elif 'shirt' in n: return 'Shirt/T-Shirt'
        elif 'kurta' in n: return 'Kurta Set'
        return 'Other'
    
    if 'Article Name' in rtv_all.columns:
        rtv_all['Category'] = rtv_all['Article Name'].apply(get_cat)
    else:
        rtv_all['Category'] = 'Other'

else:
    rtv_all = pd.DataFrame(columns=['Status', 'Date', 'Category'])

# --- TABS ---
t_daily, t1, t2, t3, t4, t5 = st.tabs(["📅 Daily Report", "📆 Monthly Trend", "📊 Category Analysis", "🚨 Missing List", "📦 SKU Report", "🗂️ Data Management"])

# 1. Daily Report
with t_daily:
    st.header("Daily Performance")
    sel_date = st.date_input("Select Date", datetime.now())
    
    d_orders = orders[orders['Date'].dt.date == sel_date] if not orders.empty and 'Date' in orders.columns else pd.DataFrame()
    d_returns = rtv_all[rtv_all['Date'].dt.date == sel_date] if not rtv_all.empty and 'Date' in rtv_all.columns else pd.DataFrame()
    
    if not d_returns.empty and 'Status' in d_returns.columns:
        d_missing = d_returns[d_returns['Status'] == 'Missing']
    else:
        d_missing = pd.DataFrame()

    c1, c2, c3 = st.columns(3)
    c1.metric("Orders", len(d_orders))
    c2.metric("Returns", len(d_returns))
    c3.metric("Missing", len(d_missing))
    
    if not d_missing.empty:
        st.subheader("Missing Items List")
        st.dataframe(d_missing, use_container_width=True)

# 2. Monthly Trend
with t1:
    st.subheader("Yearly Overview")
    curr_year = datetime.now().year
    full_year = pd.DataFrame({'Month': pd.date_range(f'{curr_year}-01-01', f'{curr_year}-12-31', freq='MS').strftime('%Y-%m')})
    
    if not orders.empty and 'Date' in orders.columns:
        o_month = orders.groupby(orders['Date'].dt.strftime('%Y-%m')).size().reset_index(name='Orders')
    else:
        o_month = pd.DataFrame(columns=['Date', 'Orders'])
        
    if not rtv_all.empty and 'Status' in rtv_all.columns and 'Date' in rtv_all.columns:
        r_month = rtv_all[rtv_all['Status']=='Matched'].groupby(rtv_all['Date'].dt.strftime('%Y-%m')).size().reset_index(name='Returns')
    else:
        r_month = pd.DataFrame(columns=['Date', 'Returns'])
        
    chart = pd.merge(full_year, o_month, left_on='Month', right_on='Date', how='left')
    chart = pd.merge(chart, r_month, left_on='Month', right_on='Date', how='left').fillna(0)
    
    st.bar_chart(chart.set_index('Month')[['Orders', 'Returns']])

# 3. Category
with t2:
    if not rtv_all.empty and 'Category' in rtv_all.columns and 'Status' in rtv_all.columns:
        c_ret = rtv_all[rtv_all['Status']=='Matched']['Category'].value_counts().reset_index(name='Returns')
        c_ret.columns = ['Category', 'Returns']
        st.dataframe(c_ret, use_container_width=True)
    else:
        st.info("No Return Data for Category Analysis.")

# 4. Missing List
with t3:
    if not rtv_all.empty and 'Status' in rtv_all.columns:
        miss = rtv_all[rtv_all['Status']=='Missing']
        st.dataframe(miss, use_container_width=True)
    else:
        st.info("No missing items.")

# 5. SKU Report
with t4:
    if not rtv_all.empty and 'SELLER SKU' in rtv_all.columns:
        s_ret = rtv_all['SELLER SKU'].value_counts().reset_index(name='Total Returns')
        st.dataframe(s_ret, use_container_width=True)
    else:
        st.info("Upload Orders/RTV to see SKU data.")

# 6. Data Management
with t5:
    st.header("🗂️ Manage Data")
    tab = st.selectbox("Select Tab", ["scans", "rtv", "orders"])
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("---")
    date_d = st.text_input("Date to Delete (YYYY-MM-DD)")
    if st.button("🗑️ Delete Data"):
        if date_d:
            delete_by_date_sheet(tab, date_d)
            st.cache_data.clear()
            time.sleep(1)
            st.rerun()
