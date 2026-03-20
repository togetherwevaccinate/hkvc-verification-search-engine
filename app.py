import pandas as pd
import streamlit as st
import os
import datetime
import plotly.express as px
import time

# 1. Page Configuration
st.set_page_config(page_title="Verification Returns & Pass Records", layout="wide")

# ----------------------------------------
# 🔒 SECURITY: TARPIT & SECRETS LOGIN
# ----------------------------------------
def check_password():
    """Returns `True` if the user had the correct password."""
    if st.session_state.get("password_correct", False):
        return True

    if "login_attempts" not in st.session_state:
        st.session_state["login_attempts"] = 0

    st.markdown("## 🔒 Restricted Access")
    st.write("Please enter the team password to access the Verification Search Engine.")
    
    if st.session_state["login_attempts"] >= 5:
        st.error("🚫 Maximum login attempts exceeded for this session. Please refresh the page to try again.")
        return False
        
    with st.form("Login_Form"):
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Log In")
        
        if submit:
            try:
                correct_password = st.secrets["password"]
            except Exception:
                st.error("⚠️ App Secret not configured properly. Please add 'password' to Streamlit Secrets.")
                return False

            if password == correct_password:
                st.session_state["password_correct"] = True
                st.session_state["login_attempts"] = 0 
                st.rerun()
            else:
                time.sleep(3) 
                st.session_state["login_attempts"] += 1
                attempts_left = 5 - st.session_state["login_attempts"]
                st.error(f"❌ Incorrect password. You have {attempts_left} attempts remaining.")
    return False

# Stop the app from loading anything else if the password is wrong or hasn't been entered yet
if not check_password():
    st.stop()

# ========================================
# 🔓 THE REST OF THE APP STARTS HERE 
# ========================================

# Get real file modified date
csv_file_path = '2026 IRR_Pass rate report - IRR.csv'
try:
    file_timestamp = os.path.getmtime(csv_file_path)
    update_date = datetime.datetime.fromtimestamp(file_timestamp).strftime("%B %d, %Y")
except FileNotFoundError:
    update_date = "Unknown Date"

# Display the title
st.title(f"👟 Hong Kong VC Verification Search Engine 1.0 ({update_date} Updated)")

# --- CACHE BUSTER ---
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
        df_sop = pd.DataFrame(columns=['Product Name', 'SOP Link', 'Description', 'SKU', 'Vertical'])

    if 'Product Name' not in df_sop.columns:
        df_sop['Product Name'] = 'Unknown'
    if 'SOP Link' not in df_sop.columns:
        df_sop['SOP Link'] = 'None'
    if 'Description' not in df_sop.columns:
        df_sop['Description'] = 'None'
    if 'SKU' not in df_sop.columns:
        df_sop['SKU'] = 'Unknown'
    if 'Vertical' not in df_sop.columns:
        df_sop['Vertical'] = 'N/A'

    if 'SKU' not in df_irr.columns:
        df_irr['SKU'] = 'Unknown'
    if 'SKU' not in df_pass.columns:
        df_pass['SKU'] = 'Unknown'

    df_sop['Product Name'] = df_sop['Product Name'].astype(str).str.strip()
    
    df_irr_clean = df_irr[['Order Number', 'Return Reason', 'Category', 'Vertical', 'Item', 'Comment', 'SKU']].copy()
    df_irr_clean.rename(columns={'Item': 'Product Name', 'Comment': 'Notes'}, inplace=True)
    df_irr_clean['Product Name'] = df_irr_clean['Product Name'].astype(str).str.strip()
    df_irr_clean['Record Source'] = 'IRR (Returned)'

    df_pass_clean = df_pass[['order_id', 'trouble_reason', 'Category', 'vertical', 'name', 'trouble_notes', 'SKU']].copy()
    df_pass_clean.rename(columns={'order_id': 'Order Number', 'trouble_reason': 'Return Reason', 'vertical': 'Vertical', 'name': 'Product Name', 'trouble_notes': 'Notes'}, inplace=True)
    df_pass_clean['Product Name'] = df_pass_clean['Product Name'].astype(str).str.strip()
    df_pass_clean['Record Source'] = 'Pass Order'

    df_combined = pd.concat([df_irr_clean, df_pass_clean], ignore_index=True)
    df_combined.dropna(subset=['Product Name', 'Order Number'], inplace=True)
    df_combined = df_combined[~df_combined['Product Name'].str.lower().isin(['nan', 'none', 'null', ''])]

    df_combined = pd.merge(df_combined, df_sop[['Product Name', 'SOP Link', 'Description']], on='Product Name', how='left')
    
    existing_products = df_combined['Product Name'].unique()
    ref_only_items = df_sop[~df_sop['Product Name'].isin(existing_products)].copy()
    ref_only_items = ref_only_items[~ref_only_items['Product Name'].str.lower().isin(['nan', 'none', 'null', ''])]
    
    if not ref_only_items.empty:
        ref_only_items['Order Number'] = 'N/A'
        ref_only_items['Return Reason'] = 'None'
        ref_only_items['Category'] = 'Reference'
        ref_only_items['Notes'] = 'No historical orders. Reference only.'
        ref_only_items['Record Source'] = 'Reference Only'
        
        df_combined = pd.concat([df_combined, ref_only_items], ignore_index=True)

    df_combined.fillna({'Notes': 'None', 'Category': 'N/A', 'Vertical': 'N/A', 'SKU': 'Unknown', 'Return Reason': 'None', 'SOP Link': 'None', 'Description': 'None'}, inplace=True)
    df_combined['SKU'] = df_combined['SKU'].astype(str).str.strip()
    
    return df_combined

df = fetch_latest_data()

def reset_to_home():
    st.session_state['text_search_bar'] = ""
    if not df.empty:
        st.session_state['source_filter'] = df['Record Source'].unique().tolist()
        st.session_state['vertical_filter'] = df['Vertical'].unique().tolist()

# ----------------------------------------
# 2. SIDEBAR (ALERTS, LEADERBOARDS & FILTERS)
# ----------------------------------------
current_search = st.session_state.get('text_search_bar', '')

if not df.empty:
    if current_search == "":
        st.sidebar.markdown("### 🚨 Recent Returns")
        
        strict_irr_data = df[
            (df['Record Source'] == 'IRR (Returned)') & 
            (~df['Return Reason'].isin(['None', 'N/A', '', 'NaN']))
        ]
        
        recent_returns = strict_irr_data.tail(3)[::-1]
        
        if not recent_returns.empty:
            for _, row in recent_returns.iterrows():
                st.sidebar.error(
                    f"**{row['Product Name']}** \n"
                    f"**SKU:** `{row['SKU']}`  \n"
                    f"**Category:** `{row['Category']}`  \n"
                    f":blue[**💬 Comment:** {row['Notes']}]"
                )
        else:
            st.sidebar.success("No recent returns found!")

        st.sidebar.markdown("---")

        st.sidebar.markdown("### 🏆 Frequent Items")
        
        irr_counts = df[df['Record Source'] == 'IRR (Returned)']['Product Name'].value_counts()
        top_returns = irr_counts[irr_counts > 1].head(3)
        
        pass_counts = df[df['Record Source'] == 'Pass Order']['Product Name'].value_counts()
        top_passes = pass_counts[pass_counts > 1].head(3)
        
        if not top_returns.empty:
            st.sidebar.markdown("**🔥 Top Returns**")
            for item, count in top_returns.items():
                st.sidebar.warning(f"**{count} Returns:** {item}")
                
        if not top_passes.empty:
            st.sidebar.write("") 
            st.sidebar.markdown("**✅ Top Passes**")
            for item, count in top_passes.items():
                st.sidebar.success(f"**{count} Passes:** {item}")
                
        st.sidebar.markdown("---")
    
    st.sidebar.header("Filter Results")
    selected_source = st.sidebar.multiselect("Record Source", df['Record Source'].unique(), default=df['Record Source'].unique(), key="source_filter")
    selected_vertical = st.sidebar.multiselect("Vertical", df['Vertical'].unique(), default=df['Vertical'].unique(), key="vertical_filter")
    
    df = df[df['Record Source'].isin(selected_source) & df['Vertical'].isin(selected_vertical)]

# ----------------------------------------
# 3. MAIN SEARCH INTERFACE
# ----------------------------------------
st.markdown("### Search Database")

col_search, col_submit, col_reset = st.columns([6, 1, 1])

with col_search:
    search_query = st.text_input("🔍 Type Name, Order #, or SKU (e.g., 'DH2920' or 'joker'):", key="text_search_bar")

with col_submit:
    st.write("") 
    st.write("") 
    st.button("🔍 Search", use_container_width=True)

with col_reset:
    st.write("") 
    st.write("") 
    st.button("🔄 Reset Home", on_click=reset_to_home, use_container_width=True)

results = pd.DataFrame()

if search_query:
    if len(search_query) < 3:
        st.warning("⚠️ Please type at least 3 characters to start searching.")
    elif not df.empty:
        query_dashed = search_query.lower().replace(" ", "-")
        query_spaced = search_query.lower()

        results = df[
            df['Product Name'].str.lower().str.contains(query_dashed, na=False) |
            df['Product Name'].str.lower().str.contains(query_spaced, na=False) |
            df['Order Number'].str.lower().str.contains(query_spaced, na=False) |
            df['SKU'].str.lower().str.contains(query_spaced, na=False)
        ]

# ----------------------------------------
# 4. DISPLAY RESULTS & ZERO RESULT LOGGING
# ----------------------------------------
if not results.empty:
    
    if 'SOP Link' not in results.columns:
        results['SOP Link'] = 'None'
    if 'Description' not in results.columns:
        results['Description'] = 'None'
    
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
                
                if product_desc != 'None' and pd.notna(product_desc) and str(product_desc).strip() != "":
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
                
                img_path_png = os.path.join("images", f"{product_name}.png")
                img_path_jpg = os.path.join("images", f"{product_name}.jpg")
                img_path_jpeg = os.path.join("images", f"{product_name}.jpeg")
                default_img_path = os.path.join("images", "default.png")
                
                if os.path.exists(img_path_png):
                    st.image(img_path_png, width=400)
                elif os.path.exists(img_path_jpg):
                    st.image(img_path_jpg, width=400)
                elif os.path.exists(img_path_jpeg):
                    st.image(img_path_jpeg, width=400)
                elif os.path.exists(default_img_path):
                    st.image(default_img_path, width=400, caption="No Main Image Available")
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
            if row['Record Source'] == 'Pass Order':
                return ['background-color: rgba(46, 160, 67, 0.15)'] * len(row)
            elif row['Record Source'] == 'IRR (Returned)':
                return ['background-color: rgba(248, 81, 73, 0.15)'] * len(row)
            elif row['Record Source'] == 'Reference Only':
                return ['background-color: rgba(128, 128, 128, 0.15)'] * len(row)
            return [''] * len(row)

        display_columns = ['Order Number', 'Product Name', 'SKU', 'Return Reason', 'Category', 'Vertical', 'Record Source']
        display_df = results[display_columns]
        styled_df = display_df.style.apply(traffic_light_colors, axis=1)
        
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        st.write("")
        with st.expander("📝 Click to read full Inspector Notes / Comments"):
            notes_data = results[(results['Notes'] != 'None') & (results['Notes'].notna())]
            if not notes_data.empty:
                for index, row in notes_data.iterrows():
                    if row['Record Source'] == 'IRR (Returned)':
                        status_icon = "❌"
                    elif row['Record Source'] == 'Pass Order':
                        status_icon = "✅"
                    else:
                        status_icon = "ℹ️"
                    st.markdown(f"**{status_icon} Order {row['Order Number']} ({row['Return Reason']}):** {row['Notes']}")
            else:
                st.info("No detailed inspector notes left for these orders.")
        
        st.write("")
        cols_to_drop = [col for col in ['SOP Link', 'Description'] if col in results.columns]
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

elif search_query:
    st.warning("No records found. Try clearing your filters or using fewer keywords.")
    
    # Silently write missing search queries to a log file
    log_file_path = "missed_searches.csv"
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_df = pd.DataFrame([{"Timestamp": timestamp, "Search Query": search_query}])
    
    if os.path.exists(log_file_path):
        log_df.to_csv(log_file_path, mode='a', header=False, index=False)
    else:
        log_df.to_csv(log_file_path, index=False)

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

# --- NEW: PASSWORD-PROTECTED ADMIN PANEL ---
with st.expander("🛠️ Admin: View Missed Searches"):
    st.caption("This log tracks items your team searched for that returned 0 results. It helps you find which items you should add to your SOP mapping!")
    
    # Require an Admin password to view the contents
    # I have also added it to pull from st.secrets if you want to hide it later!
    admin_password = st.text_input("Enter Admin Password to unlock logs:", type="password", key="admin_pw")
    
    # 🛑 DEFAULT ADMIN PASSWORD SET HERE 🛑
    correct_admin_pw = st.secrets.get("admin_password", "StockXAdmin!")
    
    if admin_password == correct_admin_pw:
        st.success("🔓 Admin access granted.")
        if os.path.exists("missed_searches.csv"):
            missed_df = pd.read_csv("missed_searches.csv")
            st.dataframe(missed_df, use_container_width=True, hide_index=True)
            
            csv_missed = missed_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Missed Searches CSV",
                data=csv_missed,
                file_name="missed_searches_log.csv",
                mime="text/csv"
            )
        else:
            st.info("No missed searches logged yet!")
    elif admin_password != "":
        st.error("❌ Incorrect Admin Password.")
