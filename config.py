from dotenv import load_dotenv
import os

load_dotenv()

# Anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL") # change as project scope changes

# Paths
INPUT_DIR="data/input"
OUTPUT_DIR="data/output"

# Property Age Threshold
# Currently single threshold, we will revisit after 10+ properties analyzed
# TODO
# Industry supports: pre_1940 / 1940-1979 / 1980-1999 / 2000-2009 / 2010+
PRE_RENOVATION_YEAR = 1980

# Rehab Cost Estimates (USD)
## 1) Age-based baselines (pre-1980 full rehab, post01980 partial)
REHAB_BASELINE_PRE_1980 = 75000 # ~$66k avg + safety margin
REHAB_BASELINE_POST_1980 = 35000 # ~$33k avg + small buffer

## 2) Property type hard caps, override age baseline if lower
REHAB_CAP_TOWNHOME = 20000  # No roof/exterior exposure
REHAB_CAP_TWO_BED_TWO_BATH = 25000  # Smaller footprint
REHAB_CAP_DEFAULT = 75000  # Single family, pre-1980

# 3) Cost Bucket Matrix --> Check the Rationale Doc for reasons
REHAB_BUCKETS_PRE_1980 = {
    "roof": (8000, 15000),
    "hvac": (6000, 12000),
    "electrical": (3000, 8000),
    "plumbing": (3000, 7000),
    "kitchen": (8000, 20000),
    "bathroom": (4000, 8000),  # per bathroom
    "flooring": (3000, 8000),
    "paint": (2000, 5000),
    "windows": (2000, 6000),
    "landscaping": (1500, 4000),
}

REHAB_BUCKETS_POST_1980 = {
    "roof": (0, 5000),
    "hvac": (0, 8000),
    "electrical": (0, 2000),
    "plumbing": (0, 3000),
    "kitchen": (5000, 15000),
    "bathroom": (3000, 6000),
    "flooring": (2000, 5000),
    "paint": (1500, 4000),
    "windows": (0, 3000),
    "landscaping": (1000, 3000),
}


# Depreciation Multipliers
## Based on 70% Rule (industry standard)
## 30% buffer covers: closing costs ~10%, holding ~4%, profit ~10%, risk ~6%
MULTIPLIER_CONSERVATIVE = 0.70   # Default — unknown market, high rates
MULTIPLIER_NEUTRAL = 0.75   # Confirmed fast DOM + positive appreciation
MULTIPLIER_FAVORABLE = 0.80   # Verified hot micro-market only, use rarely
MULTIPLIER_DEFAULT = MULTIPLIER_CONSERVATIVE  # Always start here

# Formula 
# MAB = floor_value * multiplier - rehab_cost
# Sell Profit = floor_value - (MAB + rehab_cost)
# Rental Profit = avg_area_rent * 0.90 - monthly_carrying_costs

RENTAL_DISCOUNT_RATE = 0.90   # 10% haircut for below-average performance

# State Deposit Rules
DEPOSIT_RULES = {
    "VA": {
        "method": "percentage",
        "rate": 0.05,           # 5% of list price when not in ad
        "note": "Use exact figure from ad if available"
    },
    "MD": {
        "method": "blank_cheque",
        "rate": None,
        "note": "ALERT: Blank cheque required, submit 10 min before auction"
    }
}

