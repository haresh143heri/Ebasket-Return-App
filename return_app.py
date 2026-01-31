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
    # Convert all data to string to avoid JSON errors
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
        # Keep rows that do NOT match the date
        new_df = df[df['Upload_Date'] != str(date_str)]
        
        sh = get_connection()
        worksheet = sh.worksheet(tab_name)
        worksheet.clear()
        
        if not new_df.empty:
            worksheet.update([new_df.columns.values.tolist()] + new_df.values.tolist())
        st.success(f"Deleted data for {date_str}")
    else:
        st.warning("No data found to delete.")

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
    with st.form("login_form"):
        u = st.text_input("Email")
        p = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        
        if submitted:
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
    with st.spinner("Saving data..."):
        if s_files: save_to_sheet(process(s_files), 'scans')
        if r_files: save_to_sheet(process(r_files), 'rtv')
        if o_files: save_to_sheet(process(o_files, True), 'orders')
        
        if s_files or r_files or o_files:
            st.success("Data Saved!")
            st.cache_data.clear()
            st.rerun()
        else:
            st.warning("Please select files first.")

# --- 5. Data Loading & Logic ---
@st.cache_data(ttl=60)
def load_all_data():
    return load_from_sheet('scans'), load_from_sheet('rtv'), load_from_sheet('orders')

try:
    scans, rtvs, orders = load_all_data()
except:
    st.error("Connection Failed. Please check Secrets in Settings.")
    st.stop()

# Helper for Categories
def get_cat(name):
    n = str(name).lower()
    if 'saree' in n: return 'Saree'
    elif 'shirt' in n: return 'Shirt/T-Shirt'
    elif 'kurta' in n: return 'Kurta Set'
    elif 'gown' in n: return 'Gown/Dress'
    elif 'co-ord' in n: return 'Co-Ord Set'
    return 'Other'

# Prepare Data (Handles Empty Dataframes to avoid KeyError)
scan_set = set(scans.iloc[:,0].astype(str).str.strip()) if not scans.empty else set()

if orders.empty:
    orders = pd.DataFrame(columns=['Open Order Date', 'Seller SKU ID', 'Article Name', 'Date'])
else:
    orders['Date'] = pd.to_datetime(orders['Open Order Date'], dayfirst=True, errors='coerce')

if rtvs.empty:
    rtv_all = pd.DataFrame(columns=['Return AWB No', 'Cust Order No', 'RETURN ORDER NUMBER', 'Return Created Date', 'Status', 'Date', 'Category', 'SELLER SKU'])
else:
    rtvs['Return AWB No'] = rtvs['Return AWB No'].astype(str).str.strip()
    rtvs['Cust Order No'] = rtvs['Cust Order No'].astype(str).str.strip()
    rtvs['RETURN ORDER NUMBER'] = rtvs['RETURN ORDER NUMBER'].astype(str).str.strip()
    
    rtvs['Status'] = rtvs.apply(lambda r: 'Matched' if any(str(r.get(c,'')).strip() in scan_set for c in ['Return AWB No','Cust Order No','RETURN ORDER NUMBER'] if str(r.get(c,'')) != 'nan') else 'Missing', axis=1)
    rtvs['Date'] = pd.to_datetime(rtvs['Return Created Date'].astype(str).str.replace(' IST',''), errors='coerce')
    
    pm = orders[['Seller SKU ID', 'Article Name']].drop_duplicates().rename(columns={'Seller SKU ID':'SELLER SKU'}) if not orders.empty else pd.DataFrame(columns=['SELLER SKU', 'Article Name'])
    rtv_all = pd.merge(rtvs, pm, on='SELLER SKU', how='left')
    rtv_all['Category'] = rtv_all['Article Name'].apply(get_cat)

# --- TABS ---
t_daily, t1, t2, t3, t4, t5 = st.tabs(["📅 Daily Report", "📆 Monthly Trend", "📊 Category Analysis", "🚨 Missing List", "📦 SKU Report", "🗂️ Data Management"])

# 1. Daily Report
with t_daily:
    st.header("Daily Performance")
    sel_date = st.date_input("Select Date", datetime.now())
    
    d_orders = orders[orders['Date'].dt.date == sel_date] if not orders.empty else pd.DataFrame()
    d_returns = rtv_all[rtv_all['Date'].dt.date == sel_date] if not rtv_all.empty else pd.DataFrame()
    
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
        st.dataframe(d_missing[['RETURN ORDER NUMBER', 'SELLER SKU', 'Category']], use_container_width=True)

# 2. Monthly Trend (Fixed 12 Months)
with t1:
    st.subheader("Yearly Overview")
    curr_year = datetime.now().year
    full_year = pd.DataFrame({'Month': pd.date_range(f'{curr_year}-01-01', f'{curr_year}-12-31', freq='MS').strftime('%Y-%m')})
    
    if not orders.empty:
        o_month = orders.groupby(orders['Date'].dt.strftime('%Y-%m')).size().reset_index(name='Orders')
    else:
        o_month = pd.DataFrame(columns=['Date', 'Orders'])
        
    if not rtv_all.empty and 'Status' in rtv_all.columns:
        r_month = rtv_all[rtv_all['Status']=='Matched'].groupby(rtv_all['Date'].dt.strftime('%Y-%m')).size().reset_index(name='Returns')
    else:
        r_month = pd.DataFrame(columns=['Date', 'Returns'])
        
    chart = pd.merge(full_year, o_month, left_on='Month', right_on='Date', how='left')
    chart = pd.merge(chart, r_month, left_on='Month', right_on='Date', how='left').fillna(0)
    
    st.bar_chart(chart.set_index('Month')[['Orders', 'Returns']])

# 3. Category Analysis
with t2:
    if not orders.empty and not rtv_all.empty and 'Category' in rtv_all.columns:
        c_sales = orders['Seller SKU ID'].apply(lambda x: get_cat(pm[pm['SELLER SKU']==x]['Article Name'].values[0] if x in pm['SELLER SKU'].values else '')).value_counts().reset_index(name='Sales')
        c_sales.columns = ['Category', 'Sales']
        
        c_ret = rtv_all[rtv_all['Status']=='Matched']['Category'].value_counts().reset_index(name='Returns')
        c_ret.columns = ['Category', 'Returns']
        
        c_stats = pd.merge(c_ret, c_sales, on='Category', how='left').fillna(0)
        c_stats['Ratio %'] = (c_stats['Returns'] / c_stats['Sales'] * 100).round(2)
        st.dataframe(c_stats, use_container_width=True)
    else:
        st.info("Not enough data for Category Analysis.")

# 4. Missing List
with t3:
    if not rtv_all.empty and 'Status' in rtv_all.columns:
        missing = rtv_all[rtv_all['Status']=='Missing']
        if not missing.empty:
            st.dataframe(missing[['RETURN ORDER NUMBER', 'Return AWB No', 'SELLER SKU', 'Return Created Date']], use_container_width=True)
        else:
            st.success("No missing items found!")
    else:
        st.info("No Return data available.")

# 5. SKU Report
with t4:
    if not orders.empty:
        view = st.radio("View Type", ["Aggregate (All Time)", "Daily SKU Sales"], horizontal=True)
        if view == "Aggregate (All Time)":
            s_sales = orders['Seller SKU ID'].value_counts().reset_index(name='Sales')
            s_sales.columns = ['SELLER SKU', 'Sales']
            
            if not rtv_all.empty:
                s_ret = rtv_all[rtv_all['Status']=='Matched']['SELLER SKU'].value_counts().reset_index(name='Returns')
                s_ret.columns = ['SELLER SKU', 'Returns']
            else:
                s_ret = pd.DataFrame(columns=['SELLER SKU', 'Returns'])
                
            s_stats = pd.merge(s_ret, s_sales, on='SELLER SKU', how='left').fillna(0)
            st.dataframe(s_stats.sort_values('Sales', ascending=False), use_container_width=True)
            
        else:
            d = st.date_input("Select SKU Date", datetime.now())
            do = orders[orders['Date'].dt.date == d]
            if not do.empty:
                st.dataframe(do['Seller SKU ID'].value_counts(), use_container_width=True)
            else:
                st.warning("No orders on this date.")
    else:
        st.info("Upload Order files to see SKU data.")

# 6. Data Management
with t5:
    st.header("🗂️ Manage Uploaded Data")
    tab = st.selectbox("Select Dataset", ["scans", "rtv", "orders"])
    
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("---")
    st.write("Delete data by Upload Date (YYYY-MM-DD):")
    date_d = st.text_input("Enter Date", placeholder="2026-01-31")
    
    if st.button("🗑️ Delete Data"):
        if date_d:
            delete_by_date_sheet(tab, date_d)
            st.cache_data.clear()
            time.sleep(1)
            st.rerun()
        else:
            st.error("Please enter a date.")
