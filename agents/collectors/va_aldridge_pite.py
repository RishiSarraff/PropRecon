from typing import Optional
from datetime import date, datetime
from bs4 import BeautifulSoup
from agents.collectors.base_collector import BaseCollector
from models.property_data import Source, PropertyData, Confidence
from playwright.sync_api import sync_playwright

class AldridgePiteCollector(BaseCollector):
    URL = "https://aldridgepite.com/sale-day-listings-selection/foreclosure-listings-virginia/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    def __init__(self):
        super().__init__(source=Source.ALDRIDGE_PITE)
    
    def collect(self) -> list[PropertyData]:
        result: list[PropertyData] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            # Go to disclaimer page with a 30000 ms timeout
            page.goto(self.URL, timeout=30000)
            # Click I Agree --> Cloudflare challenge passes automatically
            page.click("text=I AGREE")
            # Wait for table to appear
            page.wait_for_selector("table")
            # Change the "Show entries" select to show all rows
            # DataTables uses a select with name ending in "_length"
            page.select_option("select[name$='_length']", "-1")

            # Wait for table to re-render with all rows
            page.wait_for_timeout(2000)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "html.parser")

        listings_table = soup.find_all('table')[1]

        rows = listings_table.find_all("tr")
        self.log(f"Found {len(rows)-1} listings on listing page")
        # We do len(rows) - 1 because of the header

        for row in rows[1:]:
            newDataEntry = self._parse_row(row)
            if newDataEntry is None:
                continue

            validatedEntry = self.validate_result(newDataEntry)

            if validatedEntry.confidence != Confidence.LOW:
                result.append(validatedEntry)

        self.log(f"Collected {len(result)} properties from Aldridge Pite")
        return result

    def _parse_currency(self, value: str) -> Optional[float]:
        if not value or value.strip() == "":
            return None
        
        cleaned = value.replace("$", "").replace(",", "").strip()

        try:
            return float(cleaned)
        except ValueError:
            return None
        
    def _parse_date(self, value: str) -> Optional[date]:
        if not value or value.strip() == "":
            return None
        try:
            cleaned = " ".join(value.split())
            return datetime.strptime(cleaned, "%B %d, %Y %I:%M %p").date()
        except ValueError:
            return None
    
    def _parse_row(self, row) -> Optional[PropertyData]:
        cells = row.find_all("td")
        if len(cells) < 8:
            return None
        return PropertyData(
            source=Source.ALDRIDGE_PITE,
            address=f"{cells[1].text.strip()}, {cells[2].text.strip()}, {cells[3].text.strip()} {cells[4].text.strip()}",
            state=cells[3].text.strip(),
            auction_date=self._parse_date(cells[6].text.strip()),
            loan_amount=self._parse_currency(cells[7].text.strip())
        )
    
# apc = AldridgePiteCollector()
# apc.collect()