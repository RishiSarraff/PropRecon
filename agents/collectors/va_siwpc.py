from typing import Optional
from datetime import date
from agents.collectors.base_collector import BaseCollector
from models.property_data import Source, PropertyData, Confidence
from tools.file_reader import read_file
from playwright.sync_api import sync_playwright
import requests
import anthropic
import json
import os
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
import tempfile

class SIWPCCOllector(BaseCollector):
    
    PDF_URL = "https://www.siwpc.net/AutoUpload/Sales.pdf"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/pdf,*/*",
        "Referer": "https://www.siwpc.net/view-sales"
    }

    def __init__(self):
        super().__init__(source=Source.SIWPC)

    def collect(self):
        response = requests.get(self.PDF_URL, headers=self.headers)

        response.raise_for_status()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name
        
        read_result = read_file(tmp_path)
        os.unlink(tmp_path)

        claude_result_unstructured = self._call_claude(read_result.raw_text)

        print(claude_result_unstructured)

        result: list[PropertyData] = []

        for item in claude_result_unstructured:
            try:
                newEntry = PropertyData(
                    source = Source.SIWPC,
                    address = item.get("address"),
                    state = item.get("state"),
                    auction_date = self._parse_date(item.get("auction_date"))
                )
                validated = self.validate_result(newEntry)
                if validated.confidence != Confidence.LOW:
                    result.append(validated)
            except Exception as e:
                self.log(f"[red]Failed to parse row: {e}[/red]")
                continue

        return result

    def _call_claude(self, raw_text: str) -> list[dict]:

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": f"""You are a real estate data extraction assistant.

        Extract all property listings from this foreclosure sales report.
        The document has a hierarchy: State → County → Property rows.
        Apply the state and county context to every row beneath them.

        Return ONLY a JSON array with no explanation, no markdown, no code blocks, no em dashes.
        Each object must have exactly these fields:
        - address: full address as "street, city, VA zip"
        - state: always "VA" for this document  
        - auction_date: in format "YYYY-MM-DD"
        - county: county name

        If any field is missing, use null.

        Document:
        {raw_text}"""
            }]
        )

        raw_json = response.content[0].text
        return json.loads(raw_json)

    def _parse_date(self, value: str) -> Optional[date]:
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
        
# siwpcCollector = SIWPCCOllector()
# results = siwpcCollector.collect()
# print(f"Total: {len(results)} properties")
# for r in results[:3]:
    # print(r.address, r.auction_date)
