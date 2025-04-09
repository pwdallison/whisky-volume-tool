
import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from urllib.parse import quote_plus
from difflib import SequenceMatcher

SERP_API_KEY = "10afbab3ff5f62cec3bc85b04e7883233db7908e3b08da942f0773fb37c7c269"
SCRAPER_API_KEY = "c60c11ec758bf09739d6adaba094b889"

st.set_page_config(page_title="Whisky Retail Data Scraper", layout="wide")
st.title("🥃 Whisky Retail Data & Volume Estimator")

query = st.text_input("Enter a whisky brand or product name (leave blank for trending):")
include_amazon = st.checkbox("Include Amazon", value=True)
include_twe = st.checkbox("Include The Whisky Exchange", value=True)
include_ocado = st.checkbox("Include Ocado", value=True)
show_debug = st.checkbox("Show debug info")

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-GB,en;q=0.9"
}

def serpapi_search(query, site):
    st.write(f"🔍 Searching SerpAPI for `{query}` on `{site}`...")
    url = "https://serpapi.com/search.json"
    params = {
        "q": f"site:{site} {query}",
        "api_key": SERP_API_KEY,
        "engine": "google"
    }
    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
        urls = [res["link"] for res in data.get("organic_results", []) if site in res.get("link", "")]
        if not urls:
            st.warning(f"No SerpAPI results found for {site}.")
        return urls
    except Exception as e:
        st.error(f"SerpAPI failed for {site}: {e}")
        return []

def match_score(query, name):
    query_tokens = set(query.lower().split())
    name_tokens = set(name.lower().split())
    intersection = query_tokens.intersection(name_tokens)
    return round(len(intersection) / len(query_tokens), 2) if query_tokens else 1

def scrape_amazon(url):
    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.find(id="productTitle")
        price = soup.select_one(".a-price .a-offscreen")
        reviews = soup.select_one("#acrCustomerReviewText")
        return {
            "Retailer": "Amazon",
            "Name": title.text.strip() if title else "N/A",
            "Price": price.text.strip() if price else "N/A",
            "Reviews": int(re.sub(r"[^\d]", "", reviews.text)) if reviews else 0,
            "Availability": "In Stock" if price else "Unavailable"
        }
    except Exception as e:
        st.error(f"Amazon scrape error: {e}")
        return {"Retailer": "Amazon", "Name": "Error", "Error": str(e)}

def scrape_twe(url):
    try:
        st.write(f"🔗 Scraping TWE: {url}")
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
        st.error(f"TWE scrape error: {e}")
        return {"Retailer": "TWE", "Name": "Error", "Error": str(e)}

def scrape_ocado(url):
    try:
        st.write(f"🔗 Scraping Ocado: {url}")
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        name = soup.select_one("h1")
        price = soup.select_one("span.fop-price")
        return {
            "Retailer": "Ocado",
            "Name": name.text.strip() if name else "N/A",
            "Price": price.text.strip() if price else "N/A",
            "Reviews": "N/A",
            "Availability": "In Stock" if price else "Unavailable"
        }
    except Exception as e:
        st.error(f"Ocado scrape error: {e}")
        return {"Retailer": "Ocado", "Name": "Error", "Error": str(e)}

if st.button("Run Search"):
    with st.spinner("🔄 Running search and scrape..."):
        results = []
        if not query:
            st.error("Please enter a whisky name to search.")
            st.stop()

        if include_amazon:
            urls = serpapi_search(query, "amazon.co.uk")
            for url in urls:
                scraped = scrape_amazon(url)
                score = match_score(query, scraped.get("Name", ""))
                scraped["Match Confidence"] = f"{score * 100:.0f}%"
                results.append(scraped)
                break  # test just first result

        if include_twe:
            urls = serpapi_search(query, "thewhiskyexchange.com")
            for url in urls:
                scraped = scrape_twe(url)
                score = match_score(query, scraped.get("Name", ""))
                scraped["Match Confidence"] = f"{score * 100:.0f}%"
                results.append(scraped)
                break

        if include_ocado:
            urls = serpapi_search(query, "ocado.com")
            for url in urls:
                scraped = scrape_ocado(url)
                score = match_score(query, scraped.get("Name", ""))
                scraped["Match Confidence"] = f"{score * 100:.0f}%"
                results.append(scraped)
                break

        if results:
            df = pd.DataFrame(results)
            st.write(df)
            st.download_button("Download CSV", df.to_csv(index=False), "whisky_results.csv", "text/csv")
        else:
            st.error("⚠️ No data could be extracted.")
