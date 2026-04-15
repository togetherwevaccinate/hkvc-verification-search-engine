import pandas as pd
import streamlit as st
import os
import datetime
import plotly.express as px
import plotly.graph_objects as go
import time
import urllib.parse
import requests
import base64 # Standard Python library for encoding images into HTML

try:
    from thefuzz import process
    FUZZY_ENABLED = True
except ImportError:
    FUZZY_ENABLED = False

# 1. Page Configuration
st.set_page_config(page_title="Verification Returns & Pass Records", layout="wide")

# ----------------------------------------
# 🔒 SECURITY: GOOGLE SSO (STOCKX EMAILS ONLY)
# ----------------------------------------
def check_password():
    if st.session_state.get("email_verified", False):
        st.sidebar.caption(f"👤 Logged in as: {st.session_state.get('user_email')}")
        return True

    st.markdown("## 🔒 Restricted Access")
    st.write("This application is highly restricted. Please log in with your corporate email to access the Verification Search Engine.")

    try:
        client_id = st.secrets["client_id"]
        client_secret = st.secrets["client_secret"]
        redirect_uri = st.secrets["redirect_uri"]
    except Exception:
        st.error("⚠️ App Secrets not configured. Please add client_id, client_secret, and redirect_uri to Streamlit Secrets.")
        return False

    query_params = st.query_params
    if "code" in query_params:
        code = query_params["code"]
        
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        res = requests.post(token_url, data=data)
        
        if res.status_code == 200:
            access_token = res.json().get("access_token")
            
            user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
            user_res = requests.get(user_info_url, headers={"Authorization": f"Bearer {access_token}"})
            
            if user_res.status_code == 200:
                email = user_res.json().get("email", "")
                
                if email.endswith("@stockx.com"):
                    st.session_state["email_verified"] = True
                    st.session_state["user_email"] = email
                    st.query_params.clear() 
                    st.rerun()
                else:
                    st.error(f"🚫 Unauthorized Domain: {email}. You must use an official @stockx.com email.")
                    st.query_params.clear()
                    return False
        else:
            st.error("❌ Failed to authenticate with Google. Please try again.")
            st.query_params.clear()
            return False

    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}&response_type=code&scope=openid%20email&redirect_uri={urllib.parse.quote(redirect_uri)}"
    
    st.write("")
    st.link_button("🌐 Sign in with Google", auth_url, type="primary")
    return False

if not check_password():
    st.stop()

# ========================================
# 🔓 THE REST OF THE APP STARTS HERE 
# ========================================

csv_file_path = '2026 IRR_Pass rate report - IRR.csv'
try:
    file_timestamp = os.path.getmtime(csv_file_path)
    update_date = datetime.datetime.fromtimestamp(file_timestamp).strftime("%B %d, %Y")
except FileNotFoundError:
    update_date = "Unknown Date"

st.title(f"👟 Hong Kong VC Verification Search Engine 1.0 ({update_date} Updated)")

@st.cache_data
def fetch_latest_data():
    try:
        df_irr = pd.read_csv('2026 IRR_Pass rate report - IRR.csv', low_memory=False)
        df_pass = pd.read_csv('2026 IRR_Pass rate report - Pass order from IRR report.csv', low_memory=False)
    except FileNotFoundError:
        st.error("Main CSV files not found. Please ensure they are in the same directory.")
        return pd.DataFrame()

    try:
        df_sop = pd.read_csv('SOP_mapping.csv')
    except FileNotFoundError:
        df_sop = pd.DataFrame(columns=['Product Name', 'SOP Link', 'Description', 'SKU', 'Vertical', 'Note Date', 'Brand'])

    if 'Product Name' not in df_sop.columns: df_sop['Product Name'] = 'Unknown'
    if 'SOP Link' not in df_sop.columns: df_sop['SOP Link'] = 'None'
    if 'Description' not in df_sop.columns: df_sop['Description'] = 'None'
    if 'SKU' not in df_sop.columns: df_sop['SKU'] = 'Unknown'
    if 'Vertical' not in df_sop.columns: df_sop['Vertical'] = 'N/A'
    if 'Note Date' not in df_sop.columns: df_sop['Note Date'] = ''
    if 'Brand' not in df_sop.columns: df_sop['Brand'] = 'Unknown'

    if 'SKU' not in df_irr.columns: df_irr['SKU'] = 'Unknown'
    if 'SKU' not in df_pass.columns: df_pass['SKU'] = 'Unknown'
    if 'Exception' not in df_irr.columns: df_irr['Exception'] = 'FALSE'
    if 'Exception' not in df_pass.columns: df_pass['Exception'] = 'FALSE'
    if 'Brand' not in df_irr.columns: df_irr['Brand'] = 'Unknown'
    if 'brand' not in df_pass.columns: df_pass['brand'] = 'Unknown'
    if 'Vertical' not in df_irr.columns: df_irr['Vertical'] = 'N/A'
    if 'vertical' not in df_pass.columns: df_pass['vertical'] = 'N/A'
    if 'Category' not in df_irr.columns: df_irr['Category'] = 'N/A'
    if 'Category' not in df_pass.columns: df_pass['Category'] = 'N/A'

    df_sop['Product Name'] = df_sop['Product Name'].astype(str).str.strip()
    
    df_irr_clean = df_irr[['Order Number', 'Return Reason', 'Category', 'Vertical', 'Brand', 'Item', 'Comment', 'SKU', 'Exception']].copy()
    df_irr_clean.rename(columns={'Item': 'Product Name', 'Comment': 'Notes'}, inplace=True)
    df_irr_clean['Product Name'] = df_irr_clean['Product Name'].astype(str).str.strip()
    df_irr_clean['Record Source'] = 'IRR (Returned)'

    df_pass_clean = df_pass[['order_id', 'trouble_reason', 'Category', 'vertical', 'brand', 'name', 'trouble_notes', 'SKU', 'Exception']].copy()
    df_pass_clean.rename(columns={'order_id': 'Order Number', 'trouble_reason': 'Return Reason', 'vertical': 'Vertical', 'brand': 'Brand', 'name': 'Product Name', 'trouble_notes': 'Notes'}, inplace=True)
    df_pass_clean['Product Name'] = df_pass_clean['Product Name'].astype(str).str.strip()
    df_pass_clean['Record Source'] = 'Pass Order'

    df_combined = pd.concat([df_irr_clean, df_pass_clean], ignore_index=True)
    df_combined.dropna(subset=['Product Name', 'Order Number'], inplace=True)
    df_combined = df_combined[~df_combined['Product Name'].str.lower().isin(['nan', 'none', 'null', ''])]

    df_combined = pd.merge(df_combined, df_sop[['Product Name', 'SOP Link', 'Description', 'Note Date']], on='Product Name', how='left')
    
    existing_products = df_combined['Product Name'].unique()
    ref_only_items = df_sop[~df_sop['Product Name'].isin(existing_products)].copy()
    ref_only_items = ref_only_items[~ref_only_items['Product Name'].str.lower().isin(['nan', 'none', 'null', ''])]
    
    if not ref_only_items.empty:
        ref_only_items['Order Number'] = 'N/A'
        ref_only_items['Return Reason'] = 'None'
        ref_only_items['Category'] = 'Reference'
        ref_only_items['Notes'] = 'No historical orders. Reference only.'
        ref_only_items['Record Source'] = 'Reference Only'
        ref_only_items['Exception'] = 'FALSE' 
        df_combined = pd.concat([df_combined, ref_only_items], ignore_index=True)

    df_combined.fillna({'Notes': 'None', 'Category': 'N/A', 'Vertical': 'N/A', 'SKU': 'Unknown', 'Return Reason': 'None', 'SOP Link': 'None', 'Description': 'None', 'Note Date': '', 'Exception': 'FALSE', 'Brand': 'Unknown'}, inplace=True)
    df_combined['SKU'] = df_combined['SKU'].astype(str).str.strip()
    
    df_combined['Display_Brand'] = df_combined.apply(
        lambda row: row['Category'] if pd.isna(row['Brand']) or str(row['Brand']).strip().lower() in ['unknown', 'nan', '', 'none'] else str(row['Brand']).strip().title(), 
        axis=1
    )
    
    df_combined['Vertical'] = df_combined['Vertical'].apply(
        lambda x: str(x).strip().title() if pd.notna(x) and str(x).strip().lower() not in ['nan', 'none', ''] else 'N/A'
    )
    
    return df_combined

df = fetch_latest_data()

def reset_to_home():
    st.session_state['text_search_bar'] = ""
    st.session_state['last_logged_query'] = "" 
    st.session_state['catalog_vertical'] = "All"
    st.session_state['catalog_brand'] = "All"
    st.session_state['catalog_item'] = "Select an item..."

def get_sidebar_image(product_name):
    base_dir = "images"
    for ext in ['.png', '.jpg', '.jpeg']:
        img_path = os.path.join(base_dir, f"{product_name}{ext}")
        if os.path.exists(img_path): return img_path
    
    default_path = os.path.join(base_dir, "default.png")
    if os.path.exists(default_path): return default_path
    return None

# ----------------------------------------
# 2. SIDEBAR (ALERTS & LEADERBOARDS ONLY)
# ----------------------------------------
if not df.empty:
    st.sidebar.markdown("### 🚨 Recent Returns")
    
    strict_irr_data = df[
        (df['Record Source'] == 'IRR (Returned)') & 
        (~df['Return Reason'].isin(['None', 'N/A', '', 'NaN']))
    ]
    recent_returns = strict_irr_data.tail(3)[::-1]
    
    if not recent_returns.empty:
        for _, row in recent_returns.iterrows():
            with st.sidebar.container():
                col1, col2 = st.columns([1, 2.5])
                with col1:
                    img = get_sidebar_image(row['Product Name'])
                    if img:
                        st.image(img, use_container_width=True)
                with col2:
                    exception_status = str(row['Exception']).strip().upper()
                    is_exception = (exception_status == 'TRUE')
                    exception_badge = "<span style='color: #ff4b4b;'>🛡️ <b>Exception: No Accountability</b></span><br>" if is_exception else ""
                    
                    compact_text = (
                        f"<div style='font-size: 13px; line-height: 1.3; margin-bottom: 15px;'>"
                        f"<b>{row['Product Name']}</b><br>"
                        f"<span style='color: gray;'>SKU: {row['SKU']}</span><br>"
                        f"{exception_badge}"
                        f"<span style='color: #64b5f6;'>💬 {row['Notes']}</span>"
                        f"</div>"
                    )
                    st.markdown(compact_text, unsafe_allow_html=True)
    else:
        st.sidebar.success("No recent returns found!")

    st.sidebar.markdown("---")

    st.sidebar.markdown("### 🏆 Frequent Items")
    
    irr_counts = df[df['Record Source'] == 'IRR (Returned)']['Product Name'].value_counts()
    top_returns = irr_counts[irr_counts > 1].head(3)
    
    pass_counts = df[df['Record Source'] == 'Pass Order']['Product Name'].value_counts()
    top_passes = pass_counts[pass_counts > 1].head(3)
    
    if not top_returns.empty:
        st.sidebar.markdown("<p style='font-size: 14px; font-weight: bold; color: #ff4b4b; margin-bottom: 5px;'>❌ Top Returns</p>", unsafe_allow_html=True)
        for item, count in top_returns.items():
            with st.sidebar.container():
                col1, col2 = st.columns([1, 2.5])
                with col1:
                    img = get_sidebar_image(item)
                    if img: st.image(img, use_container_width=True)
                with col2:
                    compact_ret = (
                        f"<div style='font-size: 13px; line-height: 1.3; margin-bottom: 10px;'>"
                        f"<b>{count} Returns:</b><br>{item}"
                        f"</div>"
                    )
                    st.markdown(compact_ret, unsafe_allow_html=True)
            
    if not top_passes.empty:
        st.sidebar.markdown("<p style='font-size: 14px; font-weight: bold; color: #4caf50; margin-top: 10px; margin-bottom: 5px;'>✅ Top Passes</p>", unsafe_allow_html=True)
        for item, count in top_passes.items():
            with st.sidebar.container():
                col1, col2 = st.columns([1, 2.5])
                with col1:
                    img = get_sidebar_image(item)
                    if img: st.image(img, use_container_width=True)
                with col2:
                    compact_pass = (
                        f"<div style='font-size: 13px; line-height: 1.3; margin-bottom: 10px;'>"
                        f"<b>{count} Passes:</b><br>{item}"
                        f"</div>"
                    )
                    st.markdown(compact_pass, unsafe_allow_html=True)

# ----------------------------------------
# 3. MAIN INTERFACE: NAVIGATION
# ----------------------------------------
st.markdown("### Navigation")

nav_mode = st.radio("Choose Navigation Mode:", ["🔍 Direct Search", "🛍️ Browse Catalog", "📢 Recent SOP Updates"], horizontal=True, label_visibility="collapsed")

results = pd.DataFrame()
search_query = ""

if nav_mode == "🔍 Direct Search":
    col_search, col_submit, col_reset = st.columns([6, 1, 1])
    
    with col_search:
        search_query = st.text_input("🔍 Type Name, Order #, or SKU (e.g., 'DH2920' or 'joker'):", key="text_search_bar")
    
    with col_submit:
        st.write("") 
        st.write("") 
        search_pressed = st.button("🔍 Search", use_container_width=True)
    
    with col_reset:
        st.write("") 
        st.write("") 
        st.button("🔄 Reset Home", on_click=reset_to_home, use_container_width=True)

    if search_query:
        if len(search_query) < 3:
            st.warning("⚠️ Please type at least 3 characters to start searching.")
        else:
            if st.session_state.get('last_logged_query') != search_query:
                log_usage_path = "total_usage_log.csv"
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                usage_df = pd.DataFrame([{"Timestamp": timestamp, "Search Query": search_query}])
                
                if os.path.exists(log_usage_path): usage_df.to_csv(log_usage_path, mode='a', header=False, index=False)
                else: usage_df.to_csv(log_usage_path, index=False)
                
                st.session_state['last_logged_query'] = search_query

            if not df.empty:
                query_dashed = search_query.lower().replace(" ", "-")
                query_spaced = search_query.lower()

                results = df[
                    df['Product Name'].str.lower().str.contains(query_dashed, na=False) |
                    df['Product Name'].str.lower().str.contains(query_spaced, na=False) |
                    df['Order Number'].str.lower().str.contains(query_spaced, na=False) |
                    df['SKU'].str.lower().str.contains(query_spaced, na=False)
                ]
                
                if results.empty and FUZZY_ENABLED:
                    unique_products = df['Product Name'].dropna().unique().tolist()
                    fuzzy_matches = process.extract(search_query, unique_products, limit=3)
                    good_matches = [m[0] for m in fuzzy_matches if m[1] >= 70]
                    
                    if good_matches:
                        st.info(f"💡 No exact match found. Showing closest matches for: **{', '.join(good_matches)}**")
                        results = df[df['Product Name'].isin(good_matches)]

elif nav_mode == "🛍️ Browse Catalog":
    st.caption("Filter by Vertical and Brand to explore historical records and verification standards.")
    
    if not df.empty:
        cat_col1, cat_col2, cat_col3 = st.columns(3)
        
        with cat_col1:
            vertical_options = ["All"] + sorted(df['Vertical'].dropna().unique().tolist())
            chosen_vertical = st.selectbox("1. Choose Vertical", vertical_options, key="catalog_vertical")
            
        cat_df = df if chosen_vertical == "All" else df[df['Vertical'] == chosen_vertical]
        
        with cat_col2:
            brand_options = ["All"] + sorted(cat_df['Display_Brand'].dropna().unique().tolist())
            chosen_brand = st.selectbox("2. Choose Brand / Category", brand_options, key="catalog_brand")
            
        if chosen_brand != "All":
            cat_df = cat_df[cat_df['Display_Brand'] == chosen_brand]
            
        with cat_col3:
            item_options = ["Select an item..."] + sorted(cat_df['Product Name'].dropna().unique().tolist())
            chosen_item = st.selectbox("3. Choose Specific Item", item_options, key="catalog_item")
            
        if chosen_item != "Select an item...":
            results = cat_df[cat_df['Product Name'] == chosen_item]
            
            if st.session_state.get('last_logged_query') != f"Catalog: {chosen_item}":
                log_usage_path = "total_usage_log.csv"
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                usage_df = pd.DataFrame([{"Timestamp": timestamp, "Search Query": f"Catalog: {chosen_item}"}])
                
                if os.path.exists(log_usage_path): usage_df.to_csv(log_usage_path, mode='a', header=False, index=False)
                else: usage_df.to_csv(log_usage_path, index=False)
                st.session_state['last_logged_query'] = f"Catalog: {chosen_item}"

elif nav_mode == "📢 Recent SOP Updates":
    st.markdown("---")
    st.markdown("### 📢 Top 10 Latest SOP Updates")
    st.caption("The most recently added or modified verification standards straight from the Master Mapping Document.")
    
    if not df.empty:
        valid_dates = df[~df['Note Date'].isin(['', 'None', 'nan', None])].copy()
        
        if not valid_dates.empty:
            sop_items = valid_dates.drop_duplicates(subset=['Product Name']).copy()
            
            sop_items['Real Date'] = pd.to_datetime(sop_items['Note Date'], errors='coerce')
            sop_items = sop_items.dropna(subset=['Real Date'])
            
            top_10_sop = sop_items.sort_values(by='Real Date', ascending=False).head(10)
            
            if not top_10_sop.empty:
                for _, row in top_10_sop.iterrows():
                    with st.container():
                        st.markdown(f"#### {row['Product Name']}")
                        
                        col1, col2 = st.columns([1, 4])
                        with col1:
                            img_path = get_sidebar_image(row['Product Name'])
                            if img_path:
                                st.image(img_path, width=150)
                            else:
                                st.caption("🖼️ No Image")
                        
                        with col2:
                            st.caption(f"📅 **Updated:** {row['Note Date']} | 🏢 **Vertical:** {row['Vertical']} | 🔢 **SKU:** {row['SKU']}")
                            
                            desc_text = str(row['Description']).replace("\\n", "\n")
                            if "\n" in desc_text:
                                lines = [line.strip() for line in desc_text.split("\n") if line.strip()]
                            else:
                                lines = [line.strip() + "." for line in desc_text.split(". ") if line.strip()]
                                lines = [line.replace("..", ".") for line in lines]
                                
                            formatted_desc = "\n".join([f"👉 **{line}**" for line in lines])
                            st.info(formatted_desc)
                            
                            if row['SOP Link'] != 'None' and pd.notna(row['SOP Link']):
                                sop_links = [link.strip() for link in str(row['SOP Link']).split(',')]
                                for i, link in enumerate(sop_links):
                                    if link:
                                        btn_name = "📘 Open Internal SOP" if len(sop_links) == 1 else f"📘 Open Internal SOP (Part {i+1})"
                                        st.link_button(btn_name, link)
                    st.markdown("---")
            else:
                st.info("⚠️ Could not read the date format. Please make sure dates in SOP_mapping.csv are standard formats like MM/DD/YYYY or YYYY-MM-DD.")
        else:
            st.info("No SOP updates found yet. Add dates to the 'Note Date' column in your SOP_mapping.csv file to see them here!")


# ----------------------------------------
# 4. DISPLAY RESULTS
# ----------------------------------------
if not results.empty:
    
    if 'SOP Link' not in results.columns: results['SOP Link'] = 'None'
    if 'Description' not in results.columns: results['Description'] = 'None'
    if 'Note Date' not in results.columns: results['Note Date'] = ''
    if 'Exception' not in results.columns: results['Exception'] = 'FALSE'
    
    st.markdown("---")
    
    tab1, tab2, tab3 = st.tabs(["📊 Analytics Dashboard", "📋 Raw Data Log", "📸 Detail Photos"])
    
    with tab1:
        left_col, right_col = st.columns([3, 1])
        
        with left_col:
            total_records = len(results)
            irr_count = len(results[results['Record Source'] == 'IRR (Returned)'])
            pass_count = len(results[results['Record Source'] == 'Pass Order'])
            ref_count = len(results[results['Record Source'] == 'Reference Only'])
            
            calc_records = total_records - ref_count
            pass_rate = (pass_count / calc_records) * 100 if calc_records > 0 else 0
            
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            m_col1.metric("Total Records", total_records)
            m_col2.metric("IRR (Returned)", irr_count)
            m_col3.metric("Pass Orders", pass_count)
            m_col4.metric("Pass Rate %", f"{pass_rate:.1f}%" if calc_records > 0 else "N/A")
            
            st.write("") 
            
            defect_data = results[(results['Return Reason'] != 'None') & (results['Return Reason'].notna())]
            if not defect_data.empty:
                st.markdown("### 📊 Top Defect Reasons")
                defect_counts = defect_data['Return Reason'].value_counts().reset_index()
                defect_counts.columns = ['Defect', 'Count']
                fig = px.pie(defect_counts, values='Count', names='Defect', hole=0.4)
                fig.update_layout(margin=dict(t=10, b=10, l=10, r=10))
                st.plotly_chart(fig, use_container_width=True)
            elif ref_count == total_records:
                st.info("ℹ️ This is a Reference-Only item. No defect history exists.")
            else:
                st.success("✨ No defect history found for this search! Everything passed.")

        with right_col:
            unique_products = results['Product Name'].unique()
            if len(unique_products) > 0:
                product_name = unique_products[0]
                product_sku = results[results['Product Name'] == product_name]['SKU'].iloc[0]
                product_sop = results[results['Product Name'] == product_name]['SOP Link'].iloc[0]
                product_desc = results[results['Product Name'] == product_name]['Description'].iloc[0]
                product_note_date = results[results['Product Name'] == product_name]['Note Date'].iloc[0]
                
                if product_desc != 'None' and pd.notna(product_desc) and str(product_desc).strip() != "":
                    if product_note_date and str(product_note_date).strip() != "" and str(product_note_date).lower() != "nan":
                        st.markdown(f"### 📢 Important Notes *(Updated: {product_note_date})*")
                    else:
                        st.markdown("### 📢 Important Notes")
                        
                    desc_text = str(product_desc).replace("\\n", "\n")
                    
                    if "\n" in desc_text:
                        lines = [line.strip() for line in desc_text.split("\n") if line.strip()]
                    else:
                        lines = [line.strip() + "." for line in desc_text.split(". ") if line.strip()]
                        lines = [line.replace("..", ".") for line in lines]
                        
                    formatted_desc = "\n\n".join([f"👉 **{line}**" for line in lines])
                    st.warning(formatted_desc)
                    st.write("") 
                
                img_path = get_sidebar_image(product_name)
                if img_path:
                    st.image(img_path, width=400)
                else:
                    st.info("🖼️ No picture found. Add 'default.png' to images folder.")
                
                st.markdown(f"**Item:** {product_name}")
                if product_sku != 'Unknown':
                    st.markdown(f"**SKU:** `{product_sku}`")
                
                st.write("")
                st.markdown("**🔗 Quick Links:**")
                
                stockx_url = f"https://stockx.com/{product_name.lower()}"
                st.link_button("🌐 StockX Live", stockx_url, use_container_width=True)
                
                if product_sop != 'None' and pd.notna(product_sop):
                    sop_links = [link.strip() for link in str(product_sop).split(',')]
                    for i, link in enumerate(sop_links):
                        if link: 
                            btn_name = "📘 Internal SOP" if len(sop_links) == 1 else f"📘 Internal SOP (Part {i+1})"
                            st.link_button(btn_name, link, use_container_width=True)
    
    with tab2:
        st.warning("⚠️ **Disclaimer:** Do not solely rely on this historical data for trouble routing. These records are case studies and should be referenced on a case-by-case basis. Please continue to leverage your own personal expertise to make the final judgment.")
        st.write("")
        
        def traffic_light_colors(row):
            if row['Record Source'] == 'Pass Order': return ['background-color: rgba(46, 160, 67, 0.15)'] * len(row)
            elif row['Record Source'] == 'IRR (Returned)': return ['background-color: rgba(248, 81, 73, 0.15)'] * len(row)
            elif row['Record Source'] == 'Reference Only': return ['background-color: rgba(128, 128, 128, 0.15)'] * len(row)
            return [''] * len(row)

        display_columns = ['Order Number', 'Product Name', 'SKU', 'Return Reason', 'Category', 'Vertical', 'Record Source', 'Exception']
        display_df = results[display_columns]
        styled_df = display_df.style.apply(traffic_light_colors, axis=1)
        
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        st.write("")
        with st.expander("📝 Click to read full Inspector Notes / Comments"):
            notes_data = results[(results['Notes'] != 'None') & (results['Notes'].notna())]
            if not notes_data.empty:
                for index, row in notes_data.iterrows():
                    if row['Record Source'] == 'IRR (Returned)': status_icon = "❌"
                    elif row['Record Source'] == 'Pass Order': status_icon = "✅"
                    else: status_icon = "ℹ️"
                    st.markdown(f"**{status_icon} Order {row['Order Number']} ({row['Return Reason']}):** {row['Notes']}")
            else:
                st.info("No detailed inspector notes left for these orders.")
        
        st.write("")
        cols_to_drop = [col for col in ['SOP Link', 'Description', 'Note Date', 'Brand', 'Display_Brand'] if col in results.columns]
        download_df = results.drop(columns=cols_to_drop)
        csv = download_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Complete Search Results as CSV",
            data=csv,
            file_name='search_results_anonymous.csv',
            mime='text/csv',
        )

    with tab3:
        st.markdown("### 📸 Extra Reference & Detail Photos")
        st.caption("Detailed physical shots and reference guides for this item.")
        
        unique_products = results['Product Name'].unique()
        if len(unique_products) > 0:
            product_name = unique_products[0]
            detail_dir = "detail_images"
            
            if os.path.exists(detail_dir):
                valid_exts = ('.png', '.jpg', '.jpeg')
                extra_imgs = [f for f in os.listdir(detail_dir) if f.startswith(product_name) and f.lower().endswith(valid_exts)]
                
                if extra_imgs:
                    cols = st.columns(3)
                    for i, img_file in enumerate(extra_imgs):
                        with cols[i % 3]:
                            st.image(os.path.join(detail_dir, img_file), width=250, caption=img_file)
                else:
                    st.info(f"No extra detail photos found for **{product_name}**.")
                    st.caption(f"💡 Want to add some? Upload them to the `{detail_dir}` folder and name them like `{product_name}_1.jpg`, `{product_name}_2.jpg`, etc.")
            else:
                st.info("📂 **Feature Setup Required**")
                st.write(f"To use this feature, create a new folder named `detail_images` on your GitHub. Upload your extra photos there and name them like `{product_name}_1.jpg`!")

elif nav_mode == "🔍 Direct Search" and search_query and len(search_query) >= 3:
    st.warning("No records found. Try clearing your filters or using fewer keywords.")
    
    log_file_path = "missed_searches.csv"
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_df = pd.DataFrame([{"Timestamp": timestamp, "Search Query": search_query}])
    
    if st.session_state.get('last_missed_query') != search_query:
        if os.path.exists(log_file_path): log_df.to_csv(log_file_path, mode='a', header=False, index=False)
        else: log_df.to_csv(log_file_path, index=False)
        st.session_state['last_missed_query'] = search_query

# ----------------------------------------
# 5. FOOTER / SUPPORT & SUGGESTIONS
# ----------------------------------------
st.markdown("---")
st.markdown("#### 💡 Product Suggestion & Support")
st.caption("Got a new item to add or encountered an issue? **Click the copy icon in the top right of the box below**, open Slack, and send the host a message!")

suggestion_template = """Product Suggestion Form:
Item Slug (eg: http://stockx.com/New-Balance-327-Light-Beige-W) : 
Category (Sneakers/Shoes, Apparel, Accessories, Collectibles, Electronics, Handbags/Luxury, Trading Cards) : 
SKU (if necessary) : 
Encore Order (if necessary) : 
Photos (if necessary) : """

st.code(suggestion_template, language="text")

st.link_button("💬 Open Host's Slack Profile", "https://stockx.enterprise.slack.com/team/U01AN8XNC9H")

# --- ADMIN PANEL WITH FULL SECRETS INTEGRATION ---
with st.expander("🛠️ Admin: View Search Logs & Analytics"):
    st.caption("Secure area to download tool usage metrics and review missing SOP items to present to management.")
    
    admin_password = st.text_input("Enter Admin Password to unlock logs:", type="password", key="admin_pw")
    
    try:
        correct_admin_pw = st.secrets["admin_password"]
    except Exception:
        correct_admin_pw = None
        st.error("⚠️ Admin Secret not configured. Please add 'admin_password' to Streamlit Secrets.")
    
    if admin_password == correct_admin_pw and correct_admin_pw is not None:
        st.success("🔓 Admin access granted.")
        
        admin_tab1, admin_tab2, admin_tab3 = st.tabs(["📈 Total Usage Log", "❌ Missed Searches Log", "📣 Slack Announcement Generator"])
        
        with admin_tab1:
            st.markdown("**Total Search Volume**")
            st.caption("Use this data to prove Adoption Rate and ROI to management.")
            if os.path.exists("total_usage_log.csv"):
                usage_df = pd.read_csv("total_usage_log.csv")
                st.dataframe(usage_df.tail(50), use_container_width=True, hide_index=True)
                
                csv_usage = usage_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Complete Usage Data",
                    data=csv_usage,
                    file_name="total_usage_log.csv",
                    mime="text/csv",
                    key="dl_usage"
                )
            else:
                st.info("No searches logged yet. Type something into the search bar above to generate the first log!")
                
        with admin_tab2:
            st.markdown("**Missed Searches (Zero Results)**")
            st.caption("These items were searched for but not found. Update your SOP_mapping.csv to include them!")
            if os.path.exists("missed_searches.csv"):
                missed_df = pd.read_csv("missed_searches.csv")
                st.dataframe(missed_df.tail(50), use_container_width=True, hide_index=True)
                
                csv_missed = missed_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Missed Searches Log",
                    data=csv_missed,
                    file_name="missed_searches_log.csv",
                    mime="text/csv",
                    key="dl_missed"
                )
            else:
                st.info("No missed searches logged yet!")
                
        with admin_tab3:
            st.markdown("**Generate Slack Alert Graphic**")
            st.caption("Click the button below to generate a formatted HTML table matching `IRR FIND.png`. **Use your OS screenshot tool (`Cmd+Shift+4` or Snipping Tool) to capture the result and paste it into Slack.**")

            if st.button("🎨 Generate Recent Returns Graphic (Tabular Format)", use_container_width=True):
                if not df.empty:
                    strict_irr_data = df[
                        (df['Record Source'] == 'IRR (Returned)') &
                        (~df['Return Reason'].isin(['None', 'N/A', '', 'NaN']))
                    ]
                    latest_returns = strict_irr_data.tail(3)[::-1]

                    if not latest_returns.empty:
                        today_str = datetime.datetime.now().strftime("%Y/%m/%d")
                        
                        # --- START HTML GENERATION ---
                        # CSS for that exact format
                        html_code = """
                        <style>
                            .irr-graphic-container {
                                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                                background-color: white;
                                color: black;
                                padding: 30px;
                                border-radius: 12px;
                                max-width: 900px;
                                margin: 20px auto;
                                border: 1px solid #e2e8f0;
                            }
                            .irr-header {
                                border-bottom: 2px solid #e2e8f0;
                                padding-bottom: 15px;
                                margin-bottom: 25px;
                            }
                            .irr-title {
                                font-size: 32px;
                                font-weight: 800;
                                margin: 0;
                                color: #1a202c;
                            }
                            .irr-subtitle {
                                font-size: 16px;
                                color: #718096;
                                margin: 5px 0 0 0;
                            }
                            .irr-row {
                                display: flex;
                                align-items: start;
                                gap: 25px;
                                padding: 20px 0;
                                border-bottom: 1px solid #edf2f7;
                            }
                            .irr-row:last-child {
                                border-bottom: none;
                            }
                            .irr-img-container {
                                width: 150px;
                                flex-shrink: 0;
                                text-align: center;
                            }
                            .irr-img-container img {
                                width: 150px;
                                height: auto;
                                object-fit: contain;
                                border-radius: 8px;
                            }
                            .irr-details {
                                flex-grow: 1;
                            }
                            .irr-tag-container {
                                display: flex;
                                gap: 10px;
                                margin-bottom: 10px;
                            }
                            .irr-tag {
                                font-size: 11px;
                                font-weight: 700;
                                text-transform: uppercase;
                                padding: 4px 10px;
                                border-radius: 15px;
                                letter-spacing: 0.5px;
                            }
                            .irr-tag-red {
                                background-color: #fff5f5;
                                color: #c53030;
                                border: 1px solid #feb2b2;
                            }
                            .irr-tag-green {
                                background-color: #f0fff4;
                                color: #2f855a;
                                border: 1px solid #9ae6b4;
                            }
                            .irr-name {
                                font-size: 18px;
                                font-weight: 700;
                                color: #1a202c;
                                margin: 0 0 15px 0;
                                line-height: 1.3;
                            }
                            .irr-note-block {
                                background-color: #f7fafc;
                                border-left: 4px solid #cbd5e1;
                                padding: 10px 15px;
                                margin-bottom: 10px;
                            }
                            .irr-note-label {
                                font-weight: 600;
                                color: #4a5568;
                                font-size: 14px;
                            }
                            .irr-note-text {
                                color: #1a202c;
                                font-size: 14px;
                                margin-top: 3px;
                            }
                            .irr-reason-block {
                                display: flex;
                                gap: 8px;
                                align-items: center;
                                color: #c53030;
                                font-weight: 600;
                                font-size: 14px;
                            }
                            .irr-actions {
                                width: 140px;
                                flex-shrink: 0;
                                display: flex;
                                flex-direction: column;
                                gap: 8px;
                                padding-top: 5px;
                            }
                            .irr-btn {
                                font-size: 12px;
                                font-weight: 600;
                                text-align: center;
                                padding: 8px;
                                border-radius: 6px;
                                text-decoration: none;
                                border: 1px solid #e2e8f0;
                            }
                            .irr-btn-white {
                                background-color: white;
                                color: #1a202c;
                            }
                            .irr-btn-blue {
                                background-color: #3182ce;
                                color: white;
                                border-color: #3182ce;
                            }
                        </style>
                        """
                        
                        html_code += f"""
                        <div class="irr-graphic-container">
                            <div class="irr-header">
                                <h1 class="irr-title">Recent IRR Find</h1>
                                <p class="irr-subtitle">High-risk items needing immediate team accountability | {today_str}</p>
                            </div>
                        """

                        for _, row in latest_returns.iterrows():
                            # Encode local images to base64 for embedding in HTML
                            img_path = get_sidebar_image(row['Product Name'])
                            if img_path:
                                with open(img_path, "rb") as image_file:
                                    encoded_img = base64.b64encode(image_file.read()).decode()
                                img_src = f"data:image/png;base64,{encoded_img}"
                            else:
                                # Default empty image placeholder style
                                img_src = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNTAiIGhlaWdodD0iMTAwIj48cmVjdCB3aWR0aD0iMTUwIiBoZWlnaHQ9IjEwMCIgc3R5bGU9ImZpbGw6I2VkZjJmNztzdHJva2U6I2NiZDVlMTtzdHJva2Utd2lkdGg6MiIgLz48dGV4dCB4PSI3NSIgeT0iNTAiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxMiIgZmlsbD0iIzcxODBlNiIgdGV4dC1hbmNob3I9Im1pZGRsZSI+Tm8gSW1hZ2U8L3RleHQ+PC9zdmc+"

                            is_exception = str(row['Exception']).strip().upper() == 'TRUE'
                            exc_text = " (🛡️ EXCEPTION)" if is_exception else ""

                            html_code += f"""
                            <div class="irr-row">
                                <div class="irr-img-container">
                                    <img src="{img_src}" alt="Product Photo">
                                </div>
                                <div class="irr-details">
                                    <div class="irr-tag-container">
                                        <div class="irr-tag irr-tag-red">SKU FOUND: {row['SKU']}</div>
                                        <div class="irr-tag irr-tag-green">VERTICAL: {row['Vertical']}</div>
                                    </div>
                                    <h2 class="irr-name">{row['Product Name']}</h2>
                                    
                                    <div class="irr-note-block">
                                        <div class="irr-note-label">trouble routing note added:</div>
                                        <div class="irr-note-text">{row['Notes']}</div>
                                    </div>
                                    
                                    <div class="irr-reason-block">
                                        <span>🛑</span>
                                        <span>{row['Return Reason']}{exc_text}</span>
                                    </div>
                                </div>
                                <div class="irr-actions">
                                    <div class="irr-btn irr-btn-white">🌐 StockX Live</div>
                                    <div class="irr-btn irr-btn-blue">📘 Go to Sop link</div>
                                    <div class="irr-btn irr-btn-white">📋 IRR Check Record</div>
                                </div>
                            </div>
                            """

                        html_code += "</div>"
                        
                        # --- DISPLAY IN STREAMLIT ---
                        st.markdown(html_code, unsafe_allow_html=True)
                        st.markdown("---")
                        
                        # --- Instructions ---
                        st.info("💡 **Admin Instruction:** Hover your mouse over the white graphic box above. Use your computer's screenshot tool (`Cmd+Shift+4` on Mac or Snipping Tool on Windows) to capture just the graphic, then paste it directly into Slack!")

                        st.markdown("**Copy & Paste this message with your picture:**")
                        st.code("@here 🚨 Watch out team! New high-risk IRR items hitting our warehouse today. Please check these specific defects carefully. Full details in the Verification Search Engine!", language="text")

                    else:
                        st.success("No recent returns to report!")
                else:
                    st.warning("Data is currently empty.")
    elif admin_password != "":
        time.sleep(2)
        st.error("❌ Incorrect Admin Password.")
