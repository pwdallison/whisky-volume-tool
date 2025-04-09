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

def google_search(query, site):
    headers = {"User-Agent": "Mozilla/5.0"}
    search_url = f"https://www.google.com/search?q=site:{site}+{quote_plus(query)}"
    resp = requests.get(search_url, headers=headers)
    urls = re.findall(r"https://www\." + site.replace(".", r"\.") + r"[^\s\"']+", resp.text)
    return urls[0] if urls else None

def scrape_amazon(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, "html.parser")
    title = soup.find(id="productTitle")
    reviews = soup.find(id="acrCustomerReviewText")
    price_whole = soup.find("span", class_="a-price-whole")
    price_fraction = soup.find("span", class_="a-price-fraction")
    return {
        "Retailer": "Amazon",
        "Name": title.text.strip() if title else "N/A",
        "Price": f"£{price_whole.text.strip()}.{price_fraction.text.strip()}" if price_whole and price_fraction else "N/A",
        "Reviews": int(re.sub(r"[^\d]", "", reviews.text)) if reviews else 0,
        "Availability": "In Stock" if price_whole else "Unavailable"
    }

def scrape_waitrose(url):
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "html.parser")
    name = soup.find("h1")
    price = soup.find("span", {"class": "linePrice"})
    return {
        "Retailer": "Waitrose",
        "Name": name.text.strip() if name else "N/A",
        "Price": price.text.strip() if price else "N/A",
        "Reviews": "N/A",
        "Availability": "In Stock" if price else "Unavailable"
    }

def scrape_ocado(url):
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "html.parser")
    name = soup.find("h1")
    price = soup.find("span", class_="fop-price")
    return {
        "Retailer": "Ocado",
        "Name": name.text.strip() if name else "N/A",
        "Price": price.text.strip() if price else "N/A",
        "Reviews": "N/A",
        "Availability": "In Stock" if price else "Unavailable"
    }

def scrape_tesco(url):
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "html.parser")
    name = soup.find("h1")
    price = soup.find("span", class_="value")
    return {
        "Retailer": "Tesco",
        "Name": name.text.strip() if name else "N/A",
        "Price": price.text.strip() if price else "N/A",
        "Reviews": "N/A",
        "Availability": "In Stock" if price else "Unavailable"
    }

def scrape_sainsburys(url):
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "html.parser")
    name = soup.find("h1")
    price = soup.find("span", class_="pd__cost")
    return {
        "Retailer": "Sainsbury's",
        "Name": name.text.strip() if name else "N/A",
        "Price": price.text.strip() if price else "N/A",
        "Reviews": "N/A",
        "Availability": "In Stock" if price else "Unavailable"
    }

def scrape_twe(url):
    params = {
        "api_key": SCRAPER_API_KEY,
        "url": url,
        "render": "true"
    }
    r = requests.get("http://api.scraperapi.com", params=params)
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

def match_score(query, name):
    return round(SequenceMatcher(None, query.lower(), name.lower()).ratio(), 2)

def estimate_volume(row):
    reviews = row["Reviews"] if isinstance(row["Reviews"], int) else 0
    score = match_score(query, row["Name"])
    retailer_weight = 1 if row["Availability"] == "In Stock" else 0.5
    return int(reviews * 25 * score * retailer_weight)

if st.button("Search & Estimate"):
    if not query:
        st.warning("Please enter a product name.")
        st.stop()

    results = []
    sites = {
        "amazon.co.uk": scrape_amazon,
        "waitrose.com": scrape_waitrose,
        "ocado.com": scrape_ocado,
        "tesco.com": scrape_tesco,
        "sainsburys.co.uk": scrape_sainsburys
    }

    if include_twe:
        sites["thewhiskyexchange.com"] = scrape_twe

    for site, scraper in sites.items():
        try:
            url = google_search(query, site)
            if url:
                data = scraper(url)
                data["Match Confidence"] = f"{match_score(query, data['Name']) * 100:.0f}%"
                data["Est. Bottles/Month"] = estimate_volume(data)
                results.append(data)
        except Exception as e:
            results.append({"Retailer": site, "Error": str(e)})

    if results:
        df = pd.DataFrame(results)
        st.write(df)
        st.download_button("Download CSV", df.to_csv(index=False), "whisky_data.csv", "text/csv")
    else:
        st.error("No products found across retailers.")
