import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- 1. Setup & Auth ---
# અહીં તમારી Google Sheet નું જે નામ રાખ્યું હોય તે જ લખવું
SHEET_NAME = "Ebasket_Database"

# આ ફાઈલ તમારા ફોલ્ડરમાં હોવી જોઈએ
CREDS_FILE = "credentials.json"

def get_connection():
    # જો લાઈવ સર્વર (Streamlit Cloud) પર હોઈએ તો Secrets વાપરો, નહિતર લોકલ ફાઈલ
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    try:
        # Try loading from local file first
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, scope)
        client = gspread.authorize(creds)
        return client.open(SHEET_NAME)
    except:
        # If local file not found, try Streamlit Secrets (for when you go live)
        try:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            return client.open(SHEET_NAME)
        except Exception as e:
            st.error(f"Error connecting to Google Sheets: {e}")
            st.stop()

# --- 2. Database Functions (Google Sheets) ---

def save_to_sheet(df, tab_name):
    sh = get_connection()
    worksheet = sh.worksheet(tab_name)
    
    # Pandas DF to List of Lists
    data = df.values.tolist()
    
    # Append data only (Header is handled carefully)
    # Check if sheet is empty, if yes, add headers first
    if not worksheet.get_all_values():
        header = df.columns.tolist()
        worksheet.append_row(header)
    
    worksheet.append_rows(data)

def load_from_sheet(tab_name):
    sh = get_connection()
    worksheet = sh.worksheet(tab_name)
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

def clear_sheet_tab(tab_name):
    sh = get_connection()
    worksheet = sh.worksheet(tab_name)
    worksheet.clear()
    st.success(f"Cleared all data from {tab_name}")

def delete_by_date_sheet(tab_name, date_str):
    # This reads all data, filters locally, clears sheet, and writes back
    # Not efficient for millions of rows, but fine for thousands.
    df = load_from_sheet(tab_name)
    if not df.empty and 'Upload_Date' in df.columns:
        # Convert date column to string just in case
        df['Upload_Date'] = df['Upload_Date'].astype(str)
        
        # Keep rows that DO NOT match the date
        new_df = df[df['Upload_Date'] != str(date_str)]
        
        if len(new_df) < len(df):
            sh = get_connection()
            worksheet = sh.worksheet(tab_name)
            worksheet.clear()
            
            if not new_df.empty:
                worksheet.update([new_df.columns.values.tolist()] + new_df.values.tolist())
            st.success(f"Deleted data for {date_str}")
        else:
            st.warning("No data found for that date.")

# --- 3. App Config & Login ---
st.set_page_config(page_title="Ebasket Cloud Dashboard", layout="wide")

ADMIN_USER = "kushal@gmail.com"
ADMIN_PASS = "AdminKushal@721"

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🔒 Ebasket Cloud Login")
    u = st.text_input("Email")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        if u == ADMIN_USER and p == ADMIN_PASS:
            st.session_state['logged_in'] = True
            st.rerun()
        else: st.error("Invalid")
    st.stop()

# --- 4. Main Dashboard ---
st.sidebar.title("🚀 Ebasket Cloud Panel")
if st.sidebar.button("Logout"):
    st.session_state['logged_in'] = False
    st.rerun()

# Uploads
st.sidebar.header("📁 Add New Data")
s_files = st.sidebar.file_uploader("Scan Files", accept_multiple_files=True)
r_files = st.sidebar.file_uploader("RTV Files", accept_multiple_files=True)
o_files = st.sidebar.file_uploader("Order Files", accept_multiple_files=True)

# Helper: Get Category
def get_category(article_name):
    name = str(article_name).lower()
    if 'saree' in name or 'sari' in name: return 'Saree'
    elif 't-shirt' in name or 'tshirt' in name: return 'T-Shirt'
    elif 'shirt' in name: return 'Shirt'
    elif 'co-ord' in name or 'coord' in name or '2-piece' in name: return 'Co-Ord Set'
    elif 'gown' in name or 'dress' in name: return 'Dress & Gown'
    elif 'kurta' in name or 'suit' in name: return 'Kurta Suit - Set'
    elif 'tunic' in name or 'top' in name: return 'Tunic'
    else: return 'Other'

def process(files, is_order=False):
    dfs = []
    current_date = datetime.now().strftime('%Y-%m-%d')
    for f in files:
        if f.name.endswith('.csv'):
            df = pd.read_csv(f, header=1 if is_order else 0)
        else:
            df = pd.read_excel(f, header=1 if is_order else 0)
        
        if is_order and 'Seller SKU ID' not in df.columns:
            f.seek(0)
            if f.name.endswith('.csv'): df = pd.read_csv(f)
            else: df = pd.read_excel(f)
        
        # Add Metadata
        df['Upload_Date'] = current_date
        df['Source_File'] = f.name
        
        # Ensure all columns are strings/compatible for Google Sheets
        df = df.astype(str)
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

# Save Logic
if st.sidebar.button("☁️ Save to Google Sheet"):
    with st.spinner("Saving to Google Sheets... This may take a moment."):
        if s_files: 
            save_to_sheet(process(s_files), 'scans')
            st.sidebar.success("Scans Saved!")
        if r_files: 
            save_to_sheet(process(r_files), 'rtv')
            st.sidebar.success("RTV Saved!")
        if o_files: 
            save_to_sheet(process(o_files, True), 'orders')
            st.sidebar.success("Orders Saved!")
        
        if not (s_files or r_files or o_files):
            st.sidebar.warning("Select files first.")
        else:
            st.cache_data.clear() # Clear cache to show new data
            st.rerun()

# --- 5. Load Data & Analytics ---
# Use cache to prevent reloading from Google Sheets on every click (saves API quota)
@st.cache_data(ttl=60) # Auto refresh every 60 seconds
def load_all_data():
    s = load_from_sheet('scans')
    r = load_from_sheet('rtv')
    o = load_from_sheet('orders')
    return s, r, o

try:
    scans, rtvs, orders = load_all_data()
except Exception as e:
    st.error(f"Connection Error: {e}. Please check credentials.json")
    st.stop()

# --- Dashboard Logic (Same as before) ---
scan_set = set(scans.iloc[:,0].astype(str).str.strip()) if not scans.empty else set()

if not orders.empty:
    orders['Date'] = pd.to_datetime(orders['Open Order Date'], dayfirst=True, errors='coerce')
    pm = orders[['Seller SKU ID', 'Article Name']].drop_duplicates().rename(columns={'Seller SKU ID':'SELLER SKU'})
else:
    orders['Date'] = pd.to_datetime([])
    pm = pd.DataFrame(columns=['SELLER SKU', 'Article Name'])

if not rtvs.empty:
    rtvs['Return AWB No'] = rtvs['Return AWB No'].astype(str).str.strip()
    rtvs['Cust Order No'] = rtvs['Cust Order No'].astype(str).str.strip()
    rtvs['RETURN ORDER NUMBER'] = rtvs['RETURN ORDER NUMBER'].astype(str).str.strip()
    
    rtvs['Status'] = rtvs.apply(lambda r: 'Matched' if any(str(r.get(c,'')).strip() in scan_set for c in ['Return AWB No','Cust Order No','RETURN ORDER NUMBER'] if str(r.get(c,'')) != 'nan') else 'Missing', axis=1)
    rtvs['Date'] = pd.to_datetime(rtvs['Return Created Date'].astype(str).str.replace(' IST',''), errors='coerce')
    
    rtv_all = pd.merge(rtvs, pm, on='SELLER SKU', how='left')
    rtv_all['Category'] = rtv_all['Article Name'].apply(get_category)
else:
    rtv_all = pd.DataFrame(columns=['Status', 'Date', 'Category', 'SELLER SKU'])

# --- TABS ---
st.title("📊 Ebasket Live Dashboard (Google Sheets)")
t_daily, t1, t2, t3, t4, t5 = st.tabs(["📅 Daily Report", "📆 Monthly Trend", "📊 Category Analysis", "🚨 Missing List", "📦 SKU Report", "🗂️ Data Management"])

# 1. Daily
with t_daily:
    st.header("Daily Report")
    col_d1, col_d2 = st.columns([1, 3])
    with col_d1: selected_date = st.date_input("Select Date", datetime.now())
    
    daily_orders = orders[orders['Date'].dt.date == selected_date] if not orders.empty else pd.DataFrame()
    daily_returns = rtv_all[rtv_all['Date'].dt.date == selected_date] if not rtv_all.empty else pd.DataFrame()
    daily_missing = daily_returns[daily_returns['Status'] == 'Missing']
    
    dm1, dm2, dm3 = st.columns(3)
    dm1.metric("Orders", len(daily_orders))
    dm2.metric("Returns", len(daily_returns))
    dm3.metric("Missing", len(daily_missing))
    
    if not daily_returns.empty: st.dataframe(daily_returns[['RETURN ORDER NUMBER', 'SELLER SKU', 'Status', 'Category']], use_container_width=True)

# 2. Monthly
with t1:
    if not rtvs.empty or not orders.empty:
        current_year = datetime.now().year
        full_year_months = pd.date_range(start=f'{current_year}-01-01', end=f'{current_year}-12-31', freq='MS').strftime('%Y-%m')
        full_year_df = pd.DataFrame({'Month': full_year_months})

        o_month = orders.groupby(orders['Date'].dt.strftime('%Y-%m')).size().reset_index(name='Orders') if not orders.empty else pd.DataFrame(columns=['Date', 'Orders'])
        r_month = rtv_all[rtv_all['Status']=='Matched'].groupby(rtv_all['Date'].dt.strftime('%Y-%m')).size().reset_index(name='Returns') if not rtv_all.empty else pd.DataFrame(columns=['Date', 'Returns'])
        
        chart_data = pd.merge(full_year_df, o_month, left_on='Month', right_on='Date', how='left')
        chart_data = pd.merge(chart_data, r_month, left_on='Month', right_on='Date', how='left')
        chart_data['Orders'] = chart_data['Orders'].fillna(0)
        chart_data['Returns'] = chart_data['Returns'].fillna(0)
        
        st.bar_chart(chart_data.set_index('Month')[['Orders', 'Returns']])

# 3, 4, 5 Standard Tabs... (Code truncated for brevity, logic remains same)
with t2:
    if not orders.empty and not rtv_all.empty:
        c_sales = orders['Seller SKU ID'].apply(lambda x: get_category(pm[pm['SELLER SKU']==x]['Article Name'].values[0] if x in pm['SELLER SKU'].values else '')).value_counts().reset_index()
        c_sales.columns = ['Category', 'Sales']
        c_ret = rtv_all[rtv_all['Status']=='Matched']['Category'].value_counts().reset_index()
        c_ret.columns = ['Category', 'Returns']
        c_stats = pd.merge(c_ret, c_sales, on='Category', how='left').fillna(0)
        c_stats['Ratio %'] = (c_stats['Returns'] / c_stats['Sales'] * 100).round(2)
        st.dataframe(c_stats, use_container_width=True)

with t3:
    if not rtv_all.empty: st.dataframe(rtv_all[rtv_all['Status']=='Missing'][['RETURN ORDER NUMBER', 'Return AWB No', 'Cust Order No', 'SELLER SKU', 'Return Created Date']], use_container_width=True)

with t4:
    if not orders.empty:
        sku_view = st.radio("Select View", ["Aggregate", "Daily"], horizontal=True)
        if sku_view == "Aggregate":
            s_sales = orders['Seller SKU ID'].value_counts().reset_index()
            s_sales.columns = ['SELLER SKU', 'Sales']
            s_ret = rtv_all[rtv_all['Status']=='Matched']['SELLER SKU'].value_counts().reset_index() if not rtv_all.empty else pd.DataFrame(columns=['SELLER SKU', 'Returns'])
            s_ret.columns = ['SELLER SKU', 'Returns']
            s_stats = pd.merge(s_ret, s_sales, on='SELLER SKU', how='left').fillna(0)
            st.dataframe(s_stats.sort_values('Sales', ascending=False), use_container_width=True)
        else:
            sel_sku_date = st.date_input("Select SKU Date", datetime.now())
            day_orders = orders[orders['Date'].dt.date == sel_sku_date]
            if not day_orders.empty: st.dataframe(day_orders['Seller SKU ID'].value_counts(), use_container_width=True)

with t5:
    st.header("🗂️ Cloud Data Management")
    d_option = st.selectbox("Select Sheet Tab", ["scans", "rtv", "orders"])
    
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    # Generic Delete by Date logic for Sheet
    if st.button(f"🗑️ Delete Data from {d_option}"):
        st.warning("To delete specific dates, please use filters below.")
    
    # Simple Date Filter for Deletion
    date_to_del = st.text_input("Enter Date to Delete (YYYY-MM-DD)", placeholder="2026-01-25")
    if st.button("Confirm Delete by Date"):
        if date_to_del:
            delete_by_date_sheet(d_option, date_to_del)
            st.cache_data.clear()
            st.rerun()