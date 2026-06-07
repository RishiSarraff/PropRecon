from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum
from datetime import date

class PropertyType(str, Enum):
    SINGLE_FAMILY = "single_family"
    TOWNHOME = "townhome"
    CONDO = "condo"
    UNKNOWN = "unknown"

class State(str, Enum):
    VA = "VA"
    MD = "MD"

class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class Source(str, Enum):
    ALEX_COOPER = "alex_cooper"
    ALDRIDGE_PITE = "aldridge_pite"
    SIWPC = "siwpc"
    WASHINGTON_POST = "washington_post"
    XOME = "xome"

class PropertyData(BaseModel):
    # Bucket A — Collector fills directly
    source:         Source                    # which collector found this
    state:          State                     # VA or MD
    address:        str                       # full address string
    auction_date:   Optional[date]  = None    # sale date from source
    loan_amount:    Optional[float] = None    # original loan balance
    asking_price:   Optional[float] = None    # starting bid / list price (Xome, WashPost)
 
    # Bucket B — MLS Enricher fills
    beds:           Optional[int]   = None    # bedrooms
    baths:          Optional[int]   = None    # bathrooms
    sqft:           Optional[int]   = None    # square footage
    year_built:     Optional[int]   = None    # construction year
    property_type:  Optional[PropertyType] = None   # single_family / townhome / condo
    floor_price:    Optional[float] = None    # lowest neighbor comp (baseline for MAB)
    arv:            Optional[float] = None    # after repair value from MLS comps
    avg_rent:       Optional[float] = None    # area rental comps
    days_on_market: Optional[int]   = None    # local average DOM
    
    # Bucket C — Formula Engine calculates
    rehab_estimate: Optional[float] = None    # itemized bucket scoring
    mab:            Optional[float] = None    # max allowable bid
    sell_profit:    Optional[float] = None    # floor_price - (mab + rehab_estimate)
    rental_profit:  Optional[float] = None    # avg_rent * 0.9 - carrying costs

    # Bucket D — Business rules derive
    deposit:        Optional[float] = None    # from doc if available, else VA=5% of asking
    multiplier:     Optional[float] = None    # scored from fed rate, DOM, appreciation

    # Validation
    confidence:         Optional[Confidence] = None           # high / medium / low
    flags:              list[str] = Field(default_factory=list)  # human review notes
    enrichment_sources: list[str] = Field(default_factory=list)  # which fields MLS filled