import pandas as pd
import streamlit as st
import os
import datetime
import plotly.express as px

# 1. Page Configuration
st.set_page_config(page_title="Verification Returns & Pass Records", layout="wide")

# Get real file modified date
csv_file_path = '2026 IRR_Pass rate report - IRR.csv'
try:
    file_timestamp = os.path.getmtime(csv_file_path)
    update_date = datetime.datetime.fromtimestamp(file_timestamp).strftime("%B %d, %Y")
except FileNotFoundError:
    update_date = "Unknown Date"

# Display the title
st.title(f"👟 Hong Kong VC Verification Search Engine 1.0 ({update_date} Updated)")

@st.cache_data
def load_data():
    try:
        df_irr = pd.read_csv('2026 IRR_Pass rate report - IRR.csv', low_memory=False)
        df_pass = pd.read_csv('2026 IRR_Pass rate report - Pass order from IRR report.csv', low_memory=False)
    except FileNotFoundError:
        st.error("Main CSV files not found. Please ensure they are in the same directory.")
        return pd.DataFrame()

    try:
        df_sop = pd.read_csv('SOP_mapping.csv')
    except FileNotFoundError:
        df_sop = pd.DataFrame(columns=['Product Name', 'SOP Link'])

    if 'SKU' not in df_irr.columns:
        df_irr['SKU'] = 'Unknown'
    if 'SKU' not in df_pass.columns:
        df_pass['SKU'] = 'Unknown'

    df_irr_clean = df_irr[['Order Number', 'Return Reason', 'Category', 'Vertical', 'Item', 'Comment', 'SKU']].copy()
    df_irr_clean.rename(columns={'Item': 'Product Name', 'Comment': 'Notes'}, inplace=True)
    df_irr_clean['Record Source'] = 'IRR (Returned)'

    df_pass_clean = df_pass[['order_id', 'trouble_reason', 'Category', 'vertical', 'name', 'trouble_notes', 'SKU']].copy()
    df_pass_clean.rename(columns={'order_id': 'Order Number', 'trouble_reason': 'Return Reason', 'vertical': 'Vertical', 'name': 'Product Name', 'trouble_notes': 'Notes'}, inplace=True)
    df_pass_clean['Record Source'] = 'Pass Order'

    df_combined = pd.concat([df_irr_clean, df_pass_clean], ignore_index=True)
    df_combined.dropna(subset=['Product Name', 'Order Number'], inplace=True)
    
    # Merge SOP Links into the main dataframe
    df_combined = pd.merge(df_combined, df_sop, on='Product Name', how='left')
    
    df_combined.fillna({'Notes': 'None', 'Category': 'N/A', 'Vertical': 'N/A', 'SKU': 'Unknown', 'Return Reason': 'None', 'SOP Link': 'None'}, inplace=True)
    df_combined['SKU'] = df_combined['SKU'].astype(str)
    
    return df_combined

df = load_data()

# ----------------------------------------
# 2. SIDEBAR (ALERTS & FILTERS)
# ----------------------------------------
if not df.empty:
    st.sidebar.markdown("### 🚨 Recent Returns Alert")
    st.sidebar.caption("Watch out for these recent failures:")
    
    # --- NEW: STRICT IRR-ONLY DOUBLE FILTER ---
    # Only grabs records from the IRR source AND ensures there's an actual return reason
    strict_irr_data = df[(df['Record Source'] == 'IRR (Returned)') & (df['Return Reason'] != 'None')]
    recent_returns = strict_irr_data.tail(3)[::-1]
    
    if not recent_returns.empty:
        for _, row in recent_returns.iterrows():
            st.sidebar.error(f"**{row['Product Name']}**\n\n*SKU: {row['SKU']}*\n\n**Reason:** {row['Return Reason']}")
    else:
        st.sidebar.success("No recent returns found!")

    st.sidebar.markdown("---")
    
    st.sidebar.header("Filter Results")
    selected_source = st.sidebar.multiselect("Record Source", df['Record Source'].unique(), default=df['Record Source'].unique(), key="source_filter")
    selected_vertical = st.sidebar.multiselect("Vertical", df['Vertical'].unique(), default=df['Vertical'].unique(), key="vertical_filter")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Exact Item Match**")
    all_products = ["-- View All --"] + sorted(df['Product Name'].unique().tolist())
    selected_exact_product = st.sidebar.selectbox("Find item from list:", all_products, key="exact_match_filter")

    df = df[df['Record Source'].isin(selected_source) & df['Vertical'].isin(selected_vertical)]
    if selected_exact_product != "-- View All --":
        df = df[df['Product Name'] == selected_exact_product]

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
    st.button("🔄 Reset Home", on_click=lambda: st.session_state.clear(), use_container_width=True)

results = pd.DataFrame()

if selected_exact_product != "-- View All --":
    if search_query:
        query_spaced = search_query.lower()
        results = df[df['Order Number'].str.lower().str.contains(query_spaced, na=False) | df['SKU'].str.lower().str.contains(query_spaced, na=False)]
    else:
        results = df
elif search_query:
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
# 4. DISPLAY RESULTS
# ----------------------------------------
if not results.empty:
    st.markdown("---")
    
    tab1, tab2 = st.tabs(["📊 Analytics Dashboard", "📋 Raw Data Log"])
    
    with tab1:
        left_col, right_col = st.columns([3, 1])
        
        with left_col:
            total_records = len(results)
            irr_count = len(results[results['Record Source'] == 'IRR (Returned)'])
            pass_count = len(results[results['Record Source'] == 'Pass Order'])
            
            pass_rate = (pass_count / total_records) * 100 if total_records > 0 else 0
            
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            m_col1.metric("Total Records", total_records)
            m_col2.metric("IRR (Returned)", irr_count)
            m_col3.metric("Pass Orders", pass_count)
            m_col4.metric("Pass Rate %", f"{pass_rate:.1f}%")
            
            st.write("") 
            
            defect_data = results[(results['Return Reason'] != 'None') & (results['Return Reason'].notna())]
            if not defect_data.empty:
                st.markdown("### 📊 Top Defect Reasons")
                defect_counts = defect_data['Return Reason'].value_counts().reset_index()
                defect_counts.columns = ['Defect', 'Count']
                fig = px.pie(defect_counts, values='Count', names='Defect', hole=0.4)
                fig.update_layout(margin=dict(t=10, b=10, l=10, r=10))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.success("✨ No defect history found for this search! Everything passed.")

        with right_col:
            unique_products = results['Product Name'].unique()
            if len(unique_products) > 0:
                product_name = unique_products[0]
                product_sku = results[results['Product Name'] == product_name]['SKU'].iloc[0]
                product_sop = results[results['Product Name'] == product_name]['SOP Link'].iloc[0]
                
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
                    st.image(default_img_path, width=400, caption="No Image Available")
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
        def traffic_light_colors(row):
            if row['Record Source'] == 'Pass Order':
                return ['background-color: rgba(46, 160, 67, 0.15)'] * len(row)
            elif row['Record Source'] == 'IRR (Returned)':
                return ['background-color: rgba(248, 81, 73, 0.15)'] * len(row)
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
                    status_icon = "❌" if row['Record Source'] == 'IRR (Returned)' else "✅"
                    st.markdown(f"**{status_icon} Order {row['Order Number']} ({row['Return Reason']}):** {row['Notes']}")
            else:
                st.info("No detailed inspector notes left for these orders.")
        
        st.write("")
        download_df = results.drop(columns=['SOP Link']) if 'SOP Link' in results.columns else results
        csv = download_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Complete Search Results as CSV",
            data=csv,
            file_name='search_results_anonymous.csv',
            mime='text/csv',
        )
elif search_query or selected_exact_product != "-- View All --":
    st.warning("No records found. Try clearing your filters or using fewer keywords.")
