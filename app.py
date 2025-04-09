import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from urllib.parse import quote_plus
from difflib import SequenceMatcher

SCRAPER_API_KEY = "c60c11ec758bf09739d6adaba094b889"

st.title("🥃 Multi-Retailer Whisky Volume Estimator")

query = st.text_input("Enter a whisky brand or product name:")
include_twe = st.checkbox("Include The Whisky Exchange (via ScraperAPI)")
show_debug = st.checkbox("Show debug info")

def google_search(query, site):
    headers = {"User-Agent": "Mozilla/5.0"}
    search_url = f"https://www.google.com/search?q=site:{site}+{quote_plus(query)}"
    try:
        resp = requests.get(search_url, headers=headers, timeout=10)
        urls = re.findall(r"https://www\." + site.replace(".", r"\.") + r"[^\s\"']+", resp.text)
        return urls[0] if urls else None
    except Exception:
        return None

def scrape_site(url, selectors, retailer):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        data = {"Retailer": retailer}
        for key, selector in selectors.items():
            if callable(selector):
                data[key] = selector(soup)
            else:
                el = soup.select_one(selector)
                data[key] = el.text.strip() if el else "N/A"
        return data
    except Exception as e:
        return {"Retailer": retailer, "Name": "Error", "Error": str(e)}

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

def extract_reviews_amazon(soup):
    reviews = soup.find(id="acrCustomerReviewText")
    return int(re.sub(r"[^\d]", "", reviews.text)) if reviews else 0

def match_score(query, name):
    return round(SequenceMatcher(None, query.lower(), name.lower()).ratio(), 2)

def estimate_volume(row):
    reviews = row["Reviews"] if isinstance(row["Reviews"], int) else 0
    score = match_score(query, row["Name"])
    retailer_weight = 1 if row.get("Availability") == "In Stock" else 0.5
    return int(reviews * 25 * score * retailer_weight)

if st.button("Search & Estimate"):
    if not query:
        st.warning("Please enter a product name.")
        st.stop()

    sites = {
        "Amazon": ("amazon.co.uk", {
            "Name": "#productTitle",
            "Price": "span.a-price .a-price-whole",
            "Reviews": extract_reviews_amazon,
            "Availability": lambda soup: "In Stock" if soup.select_one("#productTitle") else "Unavailable"
        }),
        "Waitrose": ("waitrose.com", {
            "Name": "h1",
            "Price": "span.linePrice",
            "Reviews": lambda soup: "N/A",
            "Availability": lambda soup: "In Stock" if soup.select_one("span.linePrice") else "Unavailable"
        }),
        "Ocado": ("ocado.com", {
            "Name": "h1",
            "Price": "span.fop-price",
            "Reviews": lambda soup: "N/A",
            "Availability": lambda soup: "In Stock" if soup.select_one("span.fop-price") else "Unavailable"
        }),
        "Tesco": ("tesco.com", {
            "Name": "h1",
            "Price": "span.value",
            "Reviews": lambda soup: "N/A",
            "Availability": lambda soup: "In Stock" if soup.select_one("span.value") else "Unavailable"
        }),
        "Sainsbury's": ("sainsburys.co.uk", {
            "Name": "h1",
            "Price": "span.pd__cost",
            "Reviews": lambda soup: "N/A",
            "Availability": lambda soup: "In Stock" if soup.select_one("span.pd__cost") else "Unavailable"
        })
    }

    if include_twe:
        sites["The Whisky Exchange"] = ("thewhiskyexchange.com", scrape_twe)

    results = []

    for retailer, config in sites.items():
        site, selectors = config
        if callable(selectors):
            url = google_search(query, site)
            if url:
                data = selectors(url)
                data["Match Confidence"] = f"{match_score(query, data['Name']) * 100:.0f}%"
                data["Est. Bottles/Month"] = estimate_volume(data)
                results.append(data)
            else:
                results.append({
                    "Retailer": retailer, "Name": "No match found", "Price": "-", "Reviews": "-",
                    "Availability": "-", "Match Confidence": "0%", "Est. Bottles/Month": 0
                })
        else:
            url = google_search(query, site)
            if url:
                data = scrape_site(url, selectors, retailer)
                data["Match Confidence"] = f"{match_score(query, data['Name']) * 100:.0f}%"
                data["Est. Bottles/Month"] = estimate_volume(data)
                results.append(data)
            else:
                results.append({
                    "Retailer": retailer, "Name": "No match found", "Price": "-", "Reviews": "-",
                    "Availability": "-", "Match Confidence": "0%", "Est. Bottles/Month": 0
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
