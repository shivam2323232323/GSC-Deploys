import streamlit as st
import pandas as pd
import json
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

def fetch_search_console_data(start_date, end_date, domain, service, dimension='page'):
    """Fetch data from Google Search Console for a given date range."""
    request = {
        'startDate': start_date,
        'endDate': end_date,
        'dimensions': [dimension],
        'rowLimit': 1000,
    }
    try:
        response = service.searchanalytics().query(siteUrl=domain, body=request).execute()
        data = response.get('rows', [])
        return pd.DataFrame([{
            'Page': row['keys'][0],
            'Clicks': row.get('clicks', 0),
            'Position': row.get('position', 0)
        } for row in data])
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame(columns=['Page', 'Clicks', 'Position'])

def identify_top_pages(df_old, df_new):
    """Identify top 8 pages with highest click drop and improvement."""
    # Merge dataframes on Page
    merged_df = pd.merge(df_old, df_new, on='Page', how='outer', suffixes=('_old', '_new')).fillna(0)

    # Debug: Log merged data
    st.write("Merged Data for Debugging:", merged_df)

    # Calculate Click Change and Avg Pos Change
    merged_df['Click Change'] = merged_df['Clicks_new'] - merged_df['Clicks_old']
    merged_df['Avg Pos Change'] = merged_df['Position_new'] - merged_df['Position_old']

    # Sort and select top 8 improved and dropped pages
    top_improved = merged_df.nlargest(8, 'Click Change')
    top_dropped = merged_df.nsmallest(8, 'Click Change')
    return top_improved, top_dropped

def generate_page_insights(top_pages, is_improvement=True):
    """Generate insights for the top pages based on click and position changes."""
    insights = []
    for _, row in top_pages.iterrows():
        if is_improvement:
            if row['Clicks_old'] == 0 and row['Click Change'] > 0:
                insights.append(f"{row['Page']} ({int(row['Click Change']):+}) started ranking on SERP with avg position {row['Position_new']:.1f}.")
            elif row['Click Change'] > 0 and row['Avg Pos Change'] < 0:
                insights.append(f"{row['Page']} ({int(row['Click Change']):+}) avg position improved from {row['Position_old']:.1f} to {row['Position_new']:.1f}.")
            else:
                insights.append(f"{row['Page']} ({int(row['Click Change']):+}) general fluctuation observed.")
        else:
            if row['Click Change'] < 0 and row['Avg Pos Change'] > 0:
                insights.append(f"{row['Page']} ({int(row['Click Change']):+}) avg position decreased from {row['Position_old']:.1f} to {row['Position_new']:.1f}.")
            else:
                insights.append(f"{row['Page']} ({int(row['Click Change']):+}) general fluctuation observed.")
    return insights

# Streamlit UI
st.title("GSC Top Pages Report")
st.sidebar.header("Configuration")

# Step 1: Upload JSON file
uploaded_file = st.sidebar.file_uploader("Upload your Service Account JSON file", type="json")
if uploaded_file:
    try:
        # Read the uploaded file and load as JSON
        file_content = json.load(uploaded_file)
        credentials = Credentials.from_service_account_info(
            file_content, scopes=['https://www.googleapis.com/auth/webmasters.readonly']
        )
        search_console_service = build('webmasters', 'v3', credentials=credentials)
        st.sidebar.success("Authentication successful!")
    except Exception as e:
        st.sidebar.error(f"Authentication failed: {e}")
        search_console_service = None
else:
    st.sidebar.info("Upload your JSON file to proceed.")
    search_console_service = None

# Step 2: Input Domain
domain = st.sidebar.text_input("Domain", "https://www.example.com/")

# Step 3: Input Date Ranges
st.sidebar.subheader("Previous Week Date Range")
prev_week_start = st.sidebar.date_input("Previous Week Start Date")
prev_week_end = st.sidebar.date_input("Previous Week End Date")

st.sidebar.subheader("Current Week Date Range")
curr_week_start = st.sidebar.date_input("Current Week Start Date")
curr_week_end = st.sidebar.date_input("Current Week End Date")

# Validate dates
if prev_week_start >= prev_week_end:
    st.sidebar.error("Previous Week Start Date must be earlier than End Date.")
if curr_week_start >= curr_week_end:
    st.sidebar.error("Current Week Start Date must be earlier than End Date.")

# Step 4: Fetch and Display Data
if st.sidebar.button("Fetch Insights"):
    if not search_console_service:
        st.error("Please upload a valid Service Account JSON file.")
    else:
        st.info("Fetching data...")

        # Fetch old and new data
        old_data = fetch_search_console_data(prev_week_start.isoformat(), prev_week_end.isoformat(), domain, search_console_service)
        new_data = fetch_search_console_data(curr_week_start.isoformat(), curr_week_end.isoformat(), domain, search_console_service)

        if old_data.empty or new_data.empty:
            st.warning("No data available for the specified dates and domain.")
        else:
            # Compare data and generate insights
            top_improved, top_dropped = identify_top_pages(old_data, new_data)

            st.subheader("Top Pages with click improvement")
            st.dataframe(top_improved[['Page', 'Click Change', 'Position_old', 'Position_new', 'Avg Pos Change']])

            st.subheader("Top Pages with click drop")
            st.dataframe(top_dropped[['Page', 'Click Change', 'Position_old', 'Position_new', 'Avg Pos Change']])

            st.subheader("Insights for Improved Pages")
            insights_improved = generate_page_insights(top_improved, is_improvement=True)
            for insight in insights_improved:
                st.write(f"- {insight}")

            st.subheader("Insights for Dropped Pages")
            insights_dropped = generate_page_insights(top_dropped, is_improvement=False)
            for insight in insights_dropped:
                st.write(f"- {insight}")
