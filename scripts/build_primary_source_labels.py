from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "benchmarks" / "primary_source_labels.v1.json"
REVIEWED_AT = "2026-08-18"
OBJECTIVE_FIELDS = (
    "legal_name",
    "official_website",
    "headquarters",
    "ownership_status",
    "stock_ticker",
)
EVIDENCE_LOCATORS = {
    "legal_name": "Form 10-K cover page: exact name of registrant",
    "official_website": "Official company site root reviewed directly",
    "headquarters": "Form 10-K cover page: principal executive offices",
    "ownership_status": "Form 10-K cover page: publicly registered common stock",
    "stock_ticker": "Form 10-K cover page: trading symbol",
}


SOURCE_METADATA = {
    "microsoft": (
        "2025-06-30",
        "https://www.sec.gov/Archives/edgar/data/789019/000095017025100235/msft-20250630.htm",
    ),
    "apple": (
        "2025-09-27",
        "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm",
    ),
    "nvidia": (
        "2026-01-25",
        "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000021/nvda-20260125.htm",
    ),
    "alphabet": (
        "2025-12-31",
        "https://www.sec.gov/Archives/edgar/data/1652044/000165204426000018/goog-20251231.htm",
    ),
    "amazon": (
        "2025-12-31",
        "https://www.sec.gov/Archives/edgar/data/1018724/000101872426000004/amzn-20251231.htm",
    ),
    "meta": (
        "2025-12-31",
        "https://www.sec.gov/Archives/edgar/data/1326801/000162828026003942/meta-20251231.htm",
    ),
    "tesla": (
        "2025-12-31",
        "https://www.sec.gov/Archives/edgar/data/1318605/000162828026003952/tsla-20251231.htm",
    ),
    "ibm": (
        "2025-12-31",
        "https://www.sec.gov/Archives/edgar/data/51143/000005114326000010/ibm-20251231.htm",
    ),
    "intel": (
        "2025-12-27",
        "https://www.sec.gov/Archives/edgar/data/50863/000005086326000011/intc-20251227.htm",
    ),
    "cisco": (
        "2025-07-26",
        "https://www.sec.gov/Archives/edgar/data/858877/000085887725000111/csco-20250726.htm",
    ),
    "oracle": (
        "2026-05-31",
        "https://www.sec.gov/Archives/edgar/data/1341439/000119312526277521/orcl-20260531.htm",
    ),
    "adobe": (
        "2025-11-28",
        "https://www.sec.gov/Archives/edgar/data/796343/000079634326000003/adbe-20251128.htm",
    ),
    "salesforce": (
        "2026-01-31",
        "https://www.sec.gov/Archives/edgar/data/1108524/000110852426000060/crm-20260131.htm",
    ),
    "amd": (
        "2025-12-27",
        "https://www.sec.gov/Archives/edgar/data/2488/000000248826000018/amd-20251227.htm",
    ),
    "netflix": (
        "2025-12-31",
        "https://www.sec.gov/Archives/edgar/data/1065280/000106528026000034/nflx-20251231.htm",
    ),
    "coca-cola": (
        "2025-12-31",
        "https://www.sec.gov/Archives/edgar/data/21344/000162828026010047/ko-20251231.htm",
    ),
    "pepsico": (
        "2025-12-27",
        "https://www.sec.gov/Archives/edgar/data/77476/000007747626000007/pep-20251227.htm",
    ),
    "nike": (
        "2026-05-31",
        "https://www.sec.gov/Archives/edgar/data/320187/000032018726000088/nke-20260531.htm",
    ),
    "walmart": (
        "2026-01-31",
        "https://www.sec.gov/Archives/edgar/data/104169/000010416926000055/wmt-20260131.htm",
    ),
    "home-depot": (
        "2026-02-01",
        "https://www.sec.gov/Archives/edgar/data/354950/000162828026019436/hd-20260201.htm",
    ),
    "jpmorgan": (
        "2025-12-31",
        "https://www.sec.gov/Archives/edgar/data/19617/000162828026008131/jpm-20251231.htm",
    ),
    "visa": (
        "2025-09-30",
        "https://www.sec.gov/Archives/edgar/data/1403161/000140316125000089/v-20250930.htm",
    ),
    "mastercard": (
        "2025-12-31",
        "https://www.sec.gov/Archives/edgar/data/1141391/000114139126000013/ma-20251231.htm",
    ),
    "boeing": (
        "2025-12-31",
        "https://www.sec.gov/Archives/edgar/data/12927/000162828026004357/ba-20251231.htm",
    ),
    "caterpillar": (
        "2025-12-31",
        "https://www.sec.gov/Archives/edgar/data/18230/000001823026000008/cat-20251231.htm",
    ),
}

# Reviewed values are intentionally stored independently from the deterministic demo fixture.
# Changing fixtures/companies.json must never rewrite the benchmark's expected answers.
REVIEWED_LABELS = {
    "microsoft": (
        "Microsoft Corporation",
        "https://www.microsoft.com/",
        "Redmond, Washington, United States",
        "MSFT",
    ),
    "apple": (
        "Apple Inc.",
        "https://www.apple.com/",
        "Cupertino, California, United States",
        "AAPL",
    ),
    "nvidia": (
        "NVIDIA Corporation",
        "https://www.nvidia.com/",
        "Santa Clara, California, United States",
        "NVDA",
    ),
    "alphabet": (
        "Alphabet Inc.",
        "https://abc.xyz/",
        "Mountain View, California, United States",
        "GOOGL",
    ),
    "amazon": (
        "Amazon.com, Inc.",
        "https://www.aboutamazon.com/",
        "Seattle, Washington, United States",
        "AMZN",
    ),
    "meta": (
        "Meta Platforms, Inc.",
        "https://about.meta.com/",
        "Menlo Park, California, United States",
        "META",
    ),
    "tesla": ("Tesla, Inc.", "https://www.tesla.com/", "Austin, Texas, United States", "TSLA"),
    "ibm": (
        "International Business Machines Corporation",
        "https://www.ibm.com/",
        "Armonk, New York, United States",
        "IBM",
    ),
    "intel": (
        "Intel Corporation",
        "https://www.intel.com/",
        "Santa Clara, California, United States",
        "INTC",
    ),
    "cisco": (
        "Cisco Systems, Inc.",
        "https://www.cisco.com/",
        "San Jose, California, United States",
        "CSCO",
    ),
    "oracle": (
        "Oracle Corporation",
        "https://www.oracle.com/",
        "Austin, Texas, United States",
        "ORCL",
    ),
    "adobe": (
        "Adobe Inc.",
        "https://www.adobe.com/",
        "San Jose, California, United States",
        "ADBE",
    ),
    "salesforce": (
        "Salesforce, Inc.",
        "https://www.salesforce.com/",
        "San Francisco, California, United States",
        "CRM",
    ),
    "amd": (
        "Advanced Micro Devices, Inc.",
        "https://www.amd.com/",
        "Santa Clara, California, United States",
        "AMD",
    ),
    "netflix": (
        "Netflix, Inc.",
        "https://about.netflix.com/",
        "Los Gatos, California, United States",
        "NFLX",
    ),
    "coca-cola": (
        "The Coca-Cola Company",
        "https://www.coca-colacompany.com/",
        "Atlanta, Georgia, United States",
        "KO",
    ),
    "pepsico": (
        "PepsiCo, Inc.",
        "https://www.pepsico.com/",
        "Purchase, New York, United States",
        "PEP",
    ),
    "nike": (
        "NIKE, Inc.",
        "https://about.nike.com/",
        "Beaverton, Oregon, United States",
        "NKE",
    ),
    "walmart": (
        "Walmart Inc.",
        "https://corporate.walmart.com/",
        "Bentonville, Arkansas, United States",
        "WMT",
    ),
    "home-depot": (
        "The Home Depot, Inc.",
        "https://corporate.homedepot.com/",
        "Atlanta, Georgia, United States",
        "HD",
    ),
    "jpmorgan": (
        "JPMorgan Chase & Co.",
        "https://www.jpmorganchase.com/",
        "New York, New York, United States",
        "JPM",
    ),
    "visa": (
        "Visa Inc.",
        "https://corporate.visa.com/",
        "San Francisco, California, United States",
        "V",
    ),
    "mastercard": (
        "Mastercard Incorporated",
        "https://www.mastercard.com/",
        "Purchase, New York, United States",
        "MA",
    ),
    "boeing": (
        "The Boeing Company",
        "https://www.boeing.com/",
        "Arlington, Virginia, United States",
        "BA",
    ),
    "caterpillar": (
        "Caterpillar Inc.",
        "https://www.caterpillar.com/",
        "Irving, Texas, United States",
        "CAT",
    ),
}


def build_document() -> dict[str, object]:
    if set(REVIEWED_LABELS) != set(SOURCE_METADATA):
        raise RuntimeError("source registry and reviewed label cohort do not match")
    sources: dict[str, object] = {}
    companies: list[dict[str, object]] = []
    for key, (name, website, headquarters, ticker) in REVIEWED_LABELS.items():
        period_end, filing_url = SOURCE_METADATA[key]
        filing_source = f"{key}_annual_filing"
        website_source = f"{key}_official_site"
        sources[filing_source] = {
            "title": f"{name} annual report on Form 10-K",
            "url": filing_url,
            "source_kind": "primary_regulatory_filing",
            "source_period_end": period_end,
            "accessed_at": REVIEWED_AT,
        }
        sources[website_source] = {
            "title": f"{name} official company website",
            "url": website,
            "source_kind": "official_company_site",
            "accessed_at": REVIEWED_AT,
        }
        reviewed_values = {
            "legal_name": name,
            "official_website": website,
            "headquarters": headquarters,
            "ownership_status": "public",
            "stock_ticker": ticker,
        }
        fields: dict[str, object] = {}
        for field_name in OBJECTIVE_FIELDS:
            source_ids = [website_source] if field_name == "official_website" else [filing_source]
            fields[field_name] = {
                "value": reviewed_values[field_name],
                "source_ids": source_ids,
                "evidence_locator": EVIDENCE_LOCATORS[field_name],
                "reviewed_at": REVIEWED_AT,
                "review_status": "verified",
            }
        companies.append({"key": key, "name": name, "fields": fields})
    return {
        "schema_version": 2,
        "benchmark_id": "primary-source-objective-v1",
        "reviewed_at": REVIEWED_AT,
        "review_method": "independent_from_fixture_primary_source_desk_review",
        "reviewer": "Codex primary-source desk review",
        "scoring_policy": {
            "included_fields": list(OBJECTIVE_FIELDS),
            "field_conventions": {
                "headquarters": "city, state, United States; postal details omitted",
                "official_website": "canonical corporate root URL",
                "ownership_status": "public when common stock is publicly registered",
                "stock_ticker": (
                    "primary common-stock symbol; Class A symbol when multiple classes trade"
                ),
            },
            "excluded_fields": {
                "founded_year": (
                    "origin dates require a cohort-wide incorporation-versus-origin rule"
                ),
                "industry": "requires a fixed taxonomy and mapping policy",
                "description": "requires a semantic scoring rubric",
                "products_services": "requires ontology and partial-credit rules",
                "geographic_markets": "requires region normalization and partial-credit rules",
                "careers_url": "redirect and regional canonicalization policy is not yet fixed",
                "linkedin_url": "external platform ownership requires a separate verification rule",
                "ceo": "volatile field requires an as-of snapshot policy",
                "employee_count_estimate": "requires date and numeric tolerance rules",
                "recent_development": "requires a dated event-selection rubric",
            },
        },
        "sources": sources,
        "companies": companies,
    }


def main() -> None:
    document = build_document()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
