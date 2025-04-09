
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

def duckduckgo_search(query, site, max_links=10):
    try:
        q = f"site:{site} {query}"
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(q)}"
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        links = soup.select("a.result__a")
        urls = []
        for a in links[:max_links]:
            href = a.get("href")
            if site in href:
                urls.append(href)
        return urls
    except Exception:
        return []

def match_score(query, name):
    query_tokens = set(query.lower().split())
    name_tokens = set(name.lower().split())
    intersection = query_tokens.intersection(name_tokens)
    return round(len(intersection) / len(query_tokens), 2) if query_tokens else 1

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

if st.button("Search & Estimate"):
    results = []
    debug_urls = []

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
        urls = duckduckgo_search(query, site, max_links=10)
        if urls:
            best_match = None
            best_score = 0
            for url in urls:
                scraped = scraper(url)
                score = match_score(query, scraped.get("Name", ""))
                if score > best_score:
                    best_score = score
                    best_match = scraped
                    best_url = url
            if best_match:
                best_match["Match Confidence"] = f"{best_score * 100:.0f}%"
                best_match["Est. Bottles/Month"] = estimate_volume(best_match)
                if show_debug:
                    best_match["Search URL"] = best_url
                results.append(best_match)
        else:
            row = {
                "Retailer": retailer,
                "Name": "No match found",
                "Price": "-",
                "Reviews": "-",
                "Availability": "-",
                "Match Confidence": "0%",
                "Est. Bottles/Month": 0
            }
            if show_debug:
                row["Search URL"] = f"https://html.duckduckgo.com/html/?q={quote_plus(f'site:{site} {query}')}"
            results.append(row)

    if results:
        df = pd.DataFrame(results)
        st.write(df)
        st.download_button("Download CSV", df.to_csv(index=False), "whisky_data.csv", "text/csv")
        if show_debug:
            st.subheader("🔍 Search URLs")
            debug_df = df[["Retailer", "Search URL"]] if "Search URL" in df.columns else None
            if debug_df is not None:
                st.write(debug_df)
    else:
        st.error("No valid results were returned.")
