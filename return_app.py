import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- 1. Setup & Auth ---
SHEET_NAME = "Ebasket_Database"
CREDS_FILE = "credentials.json"

def get_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        # Local
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, scope)
        client = gspread.authorize(creds)
        return client.open(SHEET_NAME)
    except:
        # Streamlit Cloud
        try:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            return client.open(SHEET_NAME)
        except Exception as e:
            st.error(f"Error connecting to Google Sheets: {e}")
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
    # If empty, return empty DF
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data)

def delete_by_date_sheet(tab_name, date_str):
    df = load_from_sheet(tab_name)
    if not df.empty and 'Upload_Date' in df.columns:
        df['Upload_Date'] = df['Upload_Date'].astype(str)
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

# --- 3. Page Config & Login ---
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
        else: st.error("Invalid Credentials")
    st.stop()

# --- 4. Main App ---
st.sidebar.title("🚀 Ebasket Cloud Panel")
if st.sidebar.button("Logout"):
    st.session_state['logged_in'] = False
    st.rerun()

st.sidebar.header("📁 Add New Data")
s_files = st.sidebar.file_uploader("Scan Files", accept_multiple_files=True)
r_files = st.sidebar.file_uploader("RTV Files", accept_multiple_files=True)
o_files = st.sidebar.file_uploader("Order Files", accept_multiple_files=True)

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
        
        df['Upload_Date'] = current_date
        df['Source_File'] = f.name
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

if st.sidebar.button("☁️ Save to Google Sheet"):
    with st.spinner("Saving..."):
        if s_files: save_to_sheet(process(s_files), 'scans')
        if r_files: save_to_sheet(process(r_files), 'rtv')
        if o_files: save_to_sheet(process(o_files, True), 'orders')
        
        if s_files or r_files or o_files:
            st.success("Data Saved!")
            st.cache_data.clear()
            st.rerun()
        else:
            st.warning("Please upload files first.")

# --- 5. Data Loading ---
@st.cache_data(ttl=60)
def load_all_data():
    return load_from_sheet('scans'), load_from_sheet('rtv'), load_from_sheet('orders')

try:
    scans, rtvs, orders = load_all_data()
except Exception as e:
    st.error("Connection Error. Check Secrets.")
    st.stop()

# --- Logic ---
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
    # Initialize Empty DF with correct columns to prevent KeyError
    rtv_all = pd.DataFrame(columns=['Status', 'Date', 'Category', 'SELLER SKU', 'RETURN ORDER NUMBER', 'Return AWB No', 'Cust Order No', 'Return Created Date'])

# --- TABS ---
st.title("📊 Ebasket Live Dashboard")
t_daily, t1, t2, t3, t4, t5 = st.tabs(["📅 Daily Report", "📆 Monthly Trend", "📊 Category Analysis", "🚨 Missing List", "📦 SKU Report", "🗂️ Data Management"])

# 1. Daily Report (FIXED)
with t_daily:
    st.header("Daily Report")
    c1, c2 = st.columns([1,3])
    with c1: selected_date = st.date_input("Select Date", datetime.now())
    
    # Safe Filtering
    daily_orders = orders[orders['Date'].dt.date == selected_date] if not orders.empty else pd.DataFrame()
    
    if not rtv_all.empty:
        daily_returns = rtv_all[rtv_all['Date'].dt.date == selected_date]
        if not daily_returns.empty:
            daily_missing = daily_returns[daily_returns['Status'] == 'Missing']
        else:
            daily_missing = pd.DataFrame()
    else:
        daily_returns = pd.DataFrame()
        daily_missing = pd.DataFrame()
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Orders", len(daily_orders))
    m2.metric("Returns", len(daily_returns))
    m3.metric("Missing", len(daily_missing))
    
    if not daily_returns.empty:
        st.dataframe(daily_returns[['RETURN ORDER NUMBER', 'SELLER SKU', 'Status', 'Category']], use_container_width=True)

# 2. Monthly Trend
with t1:
    if not rtvs.empty or not orders.empty:
        curr_year = datetime.now().year
        full_year = pd.DataFrame({'Month': pd.date_range(f'{curr_year}-01-01', f'{curr_year}-12-31', freq='MS').strftime('%Y-%m')})
        
        o_month = orders.groupby(orders['Date'].dt.strftime('%Y-%m')).size().reset_index(name='Orders') if not orders.empty else pd.DataFrame(columns=['Date','Orders'])
        r_month = rtv_all[rtv_all['Status']=='Matched'].groupby(rtv_all['Date'].dt.strftime('%Y-%m')).size().reset_index(name='Returns') if not rtv_all.empty else pd.DataFrame(columns=['Date','Returns'])
        
        chart = pd.merge(full_year, o_month, left_on='Month', right_on='Date', how='left')
        chart = pd.merge(chart, r_month, left_on='Month', right_on='Date', how='left').fillna(0)
        
        st.bar_chart(chart.set_index('Month')[['Orders', 'Returns']])

# 3. Category
with t2:
    if not orders.empty and not rtv_all.empty:
        c_sales = orders['Seller SKU ID'].apply(lambda x: get_category(pm[pm['SELLER SKU']==x]['Article Name'].values[0] if x in pm['SELLER SKU'].values else '')).value_counts().reset_index(name='Sales').rename(columns={'index':'Category'})
        c_ret = rtv_all[rtv_all['Status']=='Matched']['Category'].value_counts().reset_index(name='Returns').rename(columns={'index':'Category'})
        
        # Merge safely
        # Check if column names are correct (pandas version difference fix)
        c_sales_cols = c_sales.columns.tolist()
        c_ret_cols = c_ret.columns.tolist()
        # Assume col 0 is Category
        c_sales.columns = ['Category', 'Sales']
        c_ret.columns = ['Category', 'Returns']
        
        c_stats = pd.merge(c_ret, c_sales, on='Category', how='left').fillna(0)
        c_stats['Ratio %'] = (c_stats['Returns'] / c_stats['Sales'] * 100).round(2)
        st.dataframe(c_stats, use_container_width=True)

# 4. Missing
with t3:
    if not rtv_all.empty:
        st.dataframe(rtv_all[rtv_all['Status']=='Missing'][['RETURN ORDER NUMBER', 'Return AWB No', 'Cust Order No', 'SELLER SKU', 'Return Created Date']], use_container_width=True)

# 5. SKU Report
with t4:
    if not orders.empty:
        view = st.radio("View", ["Aggregate", "Daily"], horizontal=True)
        if view == "Aggregate":
            s_sales = orders['Seller SKU ID'].value_counts().reset_index(name='Sales')
            s_sales.columns = ['SELLER SKU', 'Sales']
            s_ret = rtv_all[rtv_all['Status']=='Matched']['SELLER SKU'].value_counts().reset_index(name='Returns') if not rtv_all.empty else pd.DataFrame(columns=['SELLER SKU','Returns'])
            s_ret.columns = ['SELLER SKU', 'Returns']
            
            s_stats = pd.merge(s_ret, s_sales, on='SELLER SKU', how='left').fillna(0)
            st.dataframe(s_stats.sort_values('Sales', ascending=False), use_container_width=True)
        else:
            d = st.date_input("Date", datetime.now())
            do = orders[orders['Date'].dt.date == d]
            if not do.empty: st.dataframe(do['Seller SKU ID'].value_counts(), use_container_width=True)

# 6. Data Mgmt
with t5:
    st.header("🗂️ Manage Data")
    tab = st.selectbox("Select Tab", ["scans", "rtv", "orders"])
    if st.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()
    
    date_del = st.text_input("Date to Delete (YYYY-MM-DD)")
    if st.button("Delete"):
        delete_by_date_sheet(tab, date_del)
        st.cache_data.clear()
        st.rerun()
