import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from urllib.parse import quote_plus
from difflib import SequenceMatcher

SCRAPER_API_KEY = "c60c11ec758bf09739d6adaba094b889"

st.title("🥃 Multi-Retailer Whisky Volume Estimator & Trending Tracker")

query = st.text_input("Enter a whisky brand or product name (or leave blank to find top trending):")
include_twe = st.checkbox("Include The Whisky Exchange (via ScraperAPI)", value=True)
show_debug = st.checkbox("Show debug info")

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.5993.117 Safari/537.36",
    "Accept-Language": "en-GB,en;q=0.9"
}

def google_search(query, site):
    search_url = f"https://www.google.com/search?q=site:{site}+{quote_plus(query)}"
    try:
        resp = requests.get(search_url, headers=headers, timeout=10)
        urls = re.findall(r"https://www\." + site.replace(".", r"\.") + r"[^\s\"']+", resp.text)
        return urls[0] if urls else None
    except Exception:
        return None

def scrape_amazon(url):
    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.find(id="productTitle")
        price_block = soup.select_one(".a-price .a-offscreen")
        reviews = soup.select_one("#acrCustomerReviewText")
        return {
            "Retailer": "Amazon",
            "Name": title.text.strip() if title else "N/A",
            "Price": price_block.text.strip() if price_block else "N/A",
            "Reviews": int(re.sub(r"[^\d]", "", reviews.text)) if reviews else 0,
            "Availability": "In Stock" if price_block else "Unavailable"
        }
    except Exception as e:
        return {"Retailer": "Amazon", "Name": "Error", "Error": str(e)}

def scrape_twe(url):
    try:
        params = {"api_key": SCRAPER_API_KEY, "url": url, "render": "true"}
        r = requests.get("http://api.scraperapi.com", params=params, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        name = soup.find("h1")
        price = soup.find("p", class_="product-action__price")
        return {
            "Retailer": "TWE",
            "Name": name.text.strip() if name else "N/A",
            "Price": price.text.strip() if price else "N/A",
            "Reviews": "N/A",
            "Availability": "In Stock" if price else "Unavailable"
        }
    except Exception as e:
        return {"Retailer": "TWE", "Name": "Error", "Error": str(e)}

def match_score(query, name):
    return round(SequenceMatcher(None, query.lower(), name.lower()).ratio(), 2) if query else 1

def estimate_volume(row):
    reviews = row["Reviews"] if isinstance(row["Reviews"], int) else 0
    score = match_score(query, row["Name"])
    retailer_weight = 1 if row.get("Availability") == "In Stock" else 0.5
    return int(reviews * 25 * score * retailer_weight)

def get_top_amazon_whiskies():
    url = "https://www.amazon.co.uk/Best-Sellers-Grocery-Whisky/zgbs/grocery/359013031"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select("div.zg-grid-general-faceout, div.zg-item-immersion")
        top = []
        for item in items[:30]:
            name = (
                item.select_one(".p13n-sc-truncate-desktop-type2") or
                item.select_one("._cDEzb_p13n-sc-css-line-clamp-1_1Fn1y") or
                item.select_one("div.zg-text-center-align a.a-link-normal")
            )
            reviews = item.select_one(".a-size-small")
            review_count = int(re.sub(r"[^\d]", "", reviews.text)) if reviews else 0
            top.append({
                "Retailer": "Amazon",
                "Name": name.text.strip() if name else "N/A",
                "Reviews": review_count,
                "Price": "-",
                "Availability": "Top Seller",
                "Match Confidence": "-",
                "Est. Bottles/Month": review_count * 25
            })
        return top if top else [{
            "Retailer": "Amazon",
            "Name": "⚠️ No trending whiskies parsed",
            "Reviews": "-",
            "Price": "-",
            "Availability": "-",
            "Match Confidence": "-",
            "Est. Bottles/Month": 0
        }]
    except Exception as e:
        return [{
            "Retailer": "Amazon",
            "Name": f"❌ Error: {e}",
            "Reviews": "-",
            "Price": "-",
            "Availability": "-",
            "Match Confidence": "-",
            "Est. Bottles/Month": 0
        }]

if st.button("Search & Estimate"):
    results = []

    if not query:
        st.subheader("📈 Top Trending Whiskies")
        results.extend(get_top_amazon_whiskies())
        df = pd.DataFrame(results)
        st.write(df)
        st.download_button("Download CSV", df.to_csv(index=False), "trending_whiskies.csv", "text/csv")
        st.stop()

    sites = {
        "Amazon": ("amazon.co.uk", scrape_amazon),
        "The Whisky Exchange": ("thewhiskyexchange.com", scrape_twe) if include_twe else None
    }

    for retailer, config in sites.items():
        if not config:
            continue
        site, scraper = config
        url = google_search(query, site)
        if url:
            data = scraper(url)
            data["Match Confidence"] = f"{match_score(query, data['Name']) * 100:.0f}%"
            data["Est. Bottles/Month"] = estimate_volume(data)
            results.append(data)
        else:
            results.append({
                "Retailer": retailer,
                "Name": "No match found",
                "Price": "-",
                "Reviews": "-",
                "Availability": "-",
                "Match Confidence": "0%",
                "Est. Bottles/Month": 0
            })

    if results:
        df = pd.DataFrame(results)
        st.write(df)
        st.download_button("Download CSV", df.to_csv(index=False), "whisky_data.csv", "text/csv")
        if show_debug:
            for row in results:
                st.write(f"🔍 {row['Retailer']} → {row.get('Name')}")
    else:
        st.error("No valid results were returned.")
