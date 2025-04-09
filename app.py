
import streamlit as st
import pandas as pd
from search import search_urls
from retailers.amazon import scrape_amazon
from retailers.twe import scrape_twe
from retailers.ocado import scrape_ocado
from volume_model import estimate_volume
from sheets import write_to_sheets
from datetime import datetime

# Streamlit UI Setup
st.set_page_config(page_title="Whisky Volume Tracker", layout="wide")
st.title("🥃 Whisky Sales Volume Estimator")
st.markdown("Estimate monthly bottle sales for major whisky brands across UK online retailers.")

# Input
query = st.text_input("Enter a whisky product or brand (e.g. Monkey Shoulder, Nikka, Dewar’s):")
run_button = st.button("Run Search")

# Retailer toggles
st.subheader("Select Retailers to Search")
retailers_selected = {
    "Amazon": st.checkbox("Amazon", value=True),
    "TWE": st.checkbox("The Whisky Exchange", value=True),
    "Ocado": st.checkbox("Ocado", value=True)
}

if run_button and query:
    st.info("Running scrape... please wait.")
    all_results = []

    # 1. Search URLs per retailer
    url_results = search_urls(query, retailers_selected)

    # 2. Scrape each one
    for retailer, url in url_results.items():
        if not url:
            all_results.append({
                "Retailer": retailer,
                "Product": "Not Found",
                "Price": "-",
                "Reviews": "-",
                "Availability": "-",
                "Est. Bottles/Month": 0,
                "URL": "N/A"
            })
            continue

        if retailer == "Amazon":
            data = scrape_amazon(url)
        elif retailer == "TWE":
            data = scrape_twe(url)
        elif retailer == "Ocado":
            data = scrape_ocado(url)
        else:
            data = {"Retailer": retailer, "Product": "Not Implemented"}

        data["Est. Bottles/Month"] = estimate_volume(data)
        data["URL"] = url
        all_results.append(data)

    # 3. Display results
    df = pd.DataFrame(all_results)
    st.dataframe(df)

    # 4. Save to Google Sheets
    write_to_sheets(query, df)

    # 5. Download CSV
    st.download_button("📥 Download CSV", df.to_csv(index=False), "whisky_data.csv", "text/csv")

