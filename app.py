
import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from urllib.parse import quote_plus
from difflib import SequenceMatcher

SCRAPER_API_KEY = "c60c11ec758bf09739d6adaba094b889"

st.set_page_config(page_title="Whisky Retail Data Scraper", layout="wide")
st.title("🥃 Whisky Retail Data & Volume Estimator")

query = st.text_input("Enter a whisky brand or product name (leave blank for trending):")
include_twe = st.checkbox("Include The Whisky Exchange (via ScraperAPI)", value=True)
include_ocado = st.checkbox("Include Ocado", value=True)
include_tesco = st.checkbox("Include Tesco", value=True)
include_waitrose = st.checkbox("Include Waitrose", value=True)
include_sainsburys = st.checkbox("Include Sainsbury's", value=True)
show_debug = st.checkbox("Show debug info")

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-GB,en;q=0.9"
}

def duckduckgo_search(query, site):
    try:
        q = f"site:{site} {query}"
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(q)}"
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        links = soup.select("a.result__a")
        for a in links:
            href = a.get("href")
            if site in href:
                return href
        return None
    except Exception:
        return None

def match_score(query, name):
    return round(SequenceMatcher(None, query.lower(), name.lower()).ratio(), 2) if query else 1

def estimate_volume(row):
    reviews = row["Reviews"] if isinstance(row["Reviews"], int) else 0
    score = match_score(query, row["Name"])
    retailer_weight = 1 if row.get("Availability") == "In Stock" else 0.5
    return int(reviews * 25 * score * retailer_weight)

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

def generic_scraper(url, retailer, name_selector, price_selector):
    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.select_one(name_selector)
        price = soup.select_one(price_selector)
        return {
            "Retailer": retailer,
            "Name": title.text.strip() if title else "N/A",
            "Price": price.text.strip() if price else "N/A",
            "Reviews": "N/A",
            "Availability": "In Stock" if price else "Unavailable"
        }
    except Exception as e:
        return {"Retailer": retailer, "Name": "Error", "Error": str(e)}

def get_top_amazon_whiskies():
    try:
        api_url = (
            f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}"
            "&url=https://www.amazon.co.uk/Best-Sellers-Grocery-Whisky/zgbs/grocery/359013031"
            "&render=true"
        )
        r = requests.get(api_url, headers=headers, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select("div.zg-grid-general-faceout, div.zg-item-immersion")
        top = []
        for item in items[:30]:
            name = item.select_one(".p13n-sc-truncate-desktop-type2") or item.select_one("._cDEzb_p13n-sc-css-line-clamp-1_1Fn1y")
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
        return top
    except Exception as e:
        return [{"Retailer": "Amazon", "Name": f"Error: {e}", "Reviews": "-", "Price": "-", "Availability": "-", "Match Confidence": "-", "Est. Bottles/Month": 0}]

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
        "The Whisky Exchange": ("thewhiskyexchange.com", scrape_twe) if include_twe else None,
        "Ocado": ("ocado.com", lambda url: generic_scraper(url, "Ocado", "h1", "span.fop-price")) if include_ocado else None,
        "Tesco": ("tesco.com", lambda url: generic_scraper(url, "Tesco", "h1", ".price")) if include_tesco else None,
        "Waitrose": ("waitrose.com", lambda url: generic_scraper(url, "Waitrose", "h1", "span.linePrice")) if include_waitrose else None,
        "Sainsbury's": ("sainsburys.co.uk", lambda url: generic_scraper(url, "Sainsbury's", "h1", "span.pd__cost")) if include_sainsburys else None
    }

    for retailer, config in sites.items():
        if not config:
            continue
        site, scraper = config
        url = duckduckgo_search(query, site)
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
