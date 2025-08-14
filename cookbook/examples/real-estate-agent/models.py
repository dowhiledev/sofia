from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class Listing(BaseModel):
    mls_number: str
    board_id: Optional[int] = None
    list_price: Optional[float] = None
    url: Optional[str] = None
    is_sold: Optional[bool] = None


class Features(BaseModel):
    heating: Optional[str] = None
    cooling: Optional[str] = None
    basement: Optional[str] = None
    furnished: Optional[bool] = None
    water: Optional[str] = None
    sewer: Optional[str] = None
    pool: Optional[str] = None
    lease_terms: Optional[str] = None
    garage_type: Optional[str] = None
    den: Optional[bool] = None
    family_room: Optional[bool] = None

    @field_validator("furnished", mode="before")
    @classmethod
    def _yn_to_bool_features(cls, v):
        if isinstance(v, str):
            s = v.strip().upper()
            return True if s == "Y" else False if s == "N" else None
        return v


class DetailedListing(BaseModel):
    # IDs / status
    mls_number: str
    property_class: Optional[str] = None
    sale_type: Optional[str] = None
    status: Optional[str] = None
    board_id: Optional[int] = None
    url: Optional[str] = None

    # Price & dates
    list_price: Optional[float] = None
    list_date: Optional[date] = None
    sold_price: Optional[float] = None
    sold_date: Optional[date] = None
    days_on_market: Optional[int] = None  # computed: list_date -> sold_date or today

    # Location
    address: str

    # Property basics
    property_type: Optional[str] = None
    style: Optional[str] = None
    # Deprecated/removed: sqft_range

    # Beds / Baths / Kitchens (flat)
    bedrooms: Optional[int]
    bedrooms_plus: Optional[int]
    bathrooms: Optional[float]
    kitchens: Optional[int]
    kitchens_plus: Optional[int]
    # Moved to features

    # Parking / Lot (flat)
    parking_total: Optional[int] = None
    garage_spaces: Optional[int] = None
    lot: Optional[str] = None  # e.g., "55 x 100 ft"

    # Compact features
    # Consolidated features
    features: Features = Field(default_factory=Features)

    # Brokerage / coop / remarks
    brokerage: Optional[str] = None
    coop_comp: Optional[str] = None
    description: Optional[str] = None

    # Readable lists
    nearby_amenities: List[str] = Field(default_factory=list)
    rooms: List[str] = Field(
        default_factory=list
    )  # e.g., "Main - Living: 6.45m x 5.68m (Laminate; Combined W/Dining)"

    # Pydantic v2 validators
    @field_validator("list_price", "sold_price", mode="before")
    @classmethod
    def _money_to_float(cls, v):
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        try:
            return float(str(v).replace(",", "").replace("$", "").strip())
        except ValueError:
            return None

    # removed: furnished validator moved to Features


# ---------- Conversion ----------


def to_listing(raw: dict) -> DetailedListing:
    addr = raw.get("address") or {}
    details = raw.get("details") or {}
    lot = raw.get("lot") or {}
    brokerage = (raw.get("office") or {}).get("brokerageName")

    address_str = _build_address_string(
        street_number=addr.get("streetNumber"),
        street_name=addr.get("streetName"),
        street_suffix=addr.get("streetSuffix"),
        street_dir=addr.get("streetDirection") or addr.get("streetDirectionPrefix"),
        unit=addr.get("unitNumber"),
        city=addr.get("city"),
        state=addr.get("state"),
        zip_code=addr.get("zip"),
        country=addr.get("country"),
    )

    lot_str = _lot_to_string(
        width=lot.get("width"),
        depth=lot.get("depth"),
        measurement=lot.get("measurement") or "Feet",
        fallback_dimensions=lot.get("dimensions"),
    )

    rooms_list = _rooms_to_strings(raw.get("rooms") or {})

    bathrooms_total = _compute_bathrooms(details.get("bathrooms"))
    basement = _join_nonempty(
        [details.get("basement1"), details.get("basement2")], sep="; "
    )
    cooling = details.get("airConditioning") or details.get("centralAirConditioning")

    # dates
    list_date = _safe_parse_date(raw.get("listDate"))
    sold_date = _safe_parse_date(raw.get("soldDate"))
    status_map = {
        "Sus": "Suspended",
        "Exp": "Expired",
        "Sld": "Sold",
        "Ter": "Terminated",
        "Dft": "Deal Fell Through",
        "Lsd": "Leased",
        "Sc": "Sold Conditionally",
        "Sce": "Sold Conditionally with Escape Clause (rare)",
        "Lc": "Leased Conditionally",
        "Pc": "Price Change",
        "Ext": "Extension",
        "New": "New",
        "Cs": "Coming Soon"
    }
    status = status_map.get(raw.get("lastStatus"), "Unknown")
    # compute days on market
    dom = None
    if list_date:
        end_date = sold_date if sold_date else date.today()
        try:
            dom = (end_date - list_date).days
            if dom < 0:
                dom = None
        except Exception:
            dom = None

    return DetailedListing(
        # IDs / status
        mls_number=raw.get("mlsNumber"),
        property_class=raw.get("class"),
        sale_type=raw.get("type"),
        status=status,
        board_id=raw.get("boardId"),
        url=f"https://zown.ca/{raw.get('mlsNumber')}",
        list_price=raw.get("listPrice"),
        list_date=list_date,
        sold_price=raw.get("soldPrice"),
        sold_date=sold_date,
        days_on_market=dom,
        address=address_str,
        property_type=details.get("propertyType"),
        style=details.get("style"),
        bedrooms=_safe_int(details.get("numBedrooms")),
        bedrooms_plus=_safe_int(details.get("numBedroomsPlus")),
        bathrooms=bathrooms_total,
        kitchens=_safe_int(details.get("numKitchens")),
        kitchens_plus=_safe_int(details.get("numKitchensPlus")),
        parking_total=_safe_int(details.get("numParkingSpaces")),
        garage_spaces=_safe_int(details.get("numGarageSpaces")),
        lot=lot_str,
        features=Features(
            heating=details.get("heating"),
            cooling=cooling,
            basement=basement,
            furnished=_yn_to_bool(details.get("furnished")),
            water=details.get("waterSource"),
            sewer=details.get("sewer"),
            pool=details.get("swimmingPool"),
            lease_terms=details.get("leaseTerms"),
            garage_type=details.get("garage"),
            den=_yn_to_bool(details.get("den")),
            family_room=_yn_to_bool(details.get("familyRoom")),
        ),
        brokerage=brokerage,
        coop_comp=raw.get("coopCompensation"),
        description=details.get("description"),
        nearby_amenities=(raw.get("nearby") or {}).get("ammenities") or [],
        rooms=rooms_list,
    )


# ---------- Helpers ----------


def _build_address_string(
    street_number,
    street_name,
    street_suffix,
    street_dir,
    unit,
    city,
    state,
    zip_code,
    country,
) -> str:
    parts = []
    if unit:
        parts.append(f"Unit {unit}")
    street_bits = " ".join(
        [x for x in [street_number, street_dir, street_name, street_suffix] if x]
    )
    if street_bits:
        parts.append(street_bits)
    locality = ", ".join([x for x in [city, state, zip_code] if x])
    if locality:
        parts.append(locality)
    if country:
        parts.append(country)
    return ", ".join(parts) if parts else ""


def _lot_to_string(width, depth, measurement, fallback_dimensions) -> Optional[str]:
    """Return 'W x D unit' (e.g., '55 x 100 ft'), or fallback to provided dimensions."""
    unit = {
        "Feet": "ft",
        "Foot": "ft",
        "ft": "ft",
        "Meters": "m",
        "Meter": "m",
        "m": "m",
    }.get(str(measurement).strip(), str(measurement).lower() if measurement else "")
    w = _safe_float(width)
    d = _safe_float(depth)
    if w and d:
        return f"{_trim_int(w)} x {_trim_int(d)} {unit}".strip()
    # fallback "55.00 x 100.00 Feet"
    if fallback_dimensions:
        s = str(fallback_dimensions)
        s = (
            s.replace("Feet", "ft")
            .replace("Foot", "ft")
            .replace("Meters", "m")
            .replace("Meter", "m")
        )
        return s
    return None


def _rooms_to_strings(rooms_raw: dict) -> List[str]:
    """Return list like 'Main - Living: 6.45m x 5.68m (Laminate; Combined W/Dining)'."""
    out: List[str] = []
    if not isinstance(rooms_raw, dict):
        return out
    for _, v in sorted(rooms_raw.items(), key=lambda x: _safe_int(x[0]) or 0):
        if not isinstance(v, dict):
            continue
        name = (v.get("description") or "").strip()
        level = (v.get("level") or "").strip()
        L = _safe_float(v.get("length"))
        W = _safe_float(v.get("width"))
        size = f"{_trim_int(L)}m x {_trim_int(W)}m" if L and W else None
        feats = [v.get("features"), v.get("features2"), v.get("features3")]
        feats = "; ".join([f for f in feats if f])
        left = f"{level} - {name}".strip(" -")
        if size and feats:
            out.append(f"{left}: {size} ({feats})")
        elif size:
            out.append(f"{left}: {size}")
        elif feats:
            out.append(f"{left} ({feats})")
        else:
            out.append(left)
    return out


def _compute_bathrooms(bath_dict) -> Optional[float]:
    """Simple: any listed bath counts as 1.0. Adjust if you want 2pc=0.5, 3pc=0.75, etc."""
    if not bath_dict or not isinstance(bath_dict, dict):
        return None
    total = 0
    for _, entry in bath_dict.items():
        if not entry:
            continue
        cnt = entry.get("count")
        if cnt is None or str(cnt).strip() == "":
            continue
        try:
            total += int(cnt)
        except Exception:
            continue
    return float(total) if total else None


def _safe_parse_date(v) -> Optional[date]:
    if not v:
        return None
    try:
        if isinstance(v, date) and not isinstance(v, datetime):
            return v
        if isinstance(v, datetime):
            return v.date()
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).date()
    except Exception:
        return None


def _safe_int(v) -> Optional[int]:
    try:
        if v is None or v == "":
            return None
        return int(float(v))
    except Exception:
        return None


def _safe_float(v) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except Exception:
        return None


def _trim_int(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else str(x)


def _yn_to_bool(v) -> Optional[bool]:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip().upper()
    if s == "Y":
        return True
    if s == "N":
        return False
    return None


def _join_nonempty(items, sep=", "):
    return sep.join([str(x) for x in items if x]) or None
