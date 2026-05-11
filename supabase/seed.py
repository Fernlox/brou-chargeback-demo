from __future__ import annotations

import calendar
import random
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from dotenv import load_dotenv
from supabase import Client, create_client
import os


ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"
RNG = random.Random(20260508)
DEFAULT_UYU_PER_USD = 40.0
CARD_LAST4_POOL = ("4821", "1179", "9034")
CARD_BRANDS = ("visa", "mastercard")


@dataclass(frozen=True)
class Merchant:
    name: str
    category: str
    mcc_options: tuple[str, ...]
    supported_currencies: tuple[str, ...]
    amount_ranges: dict[str, tuple[float, float]]
    is_online: bool
    countries: tuple[str, ...] = ("UY",)
    dba_name: str | None = None


MERCHANTS: tuple[Merchant, ...] = (
    Merchant(
        name="Tienda Inglesa",
        category="supermarket",
        mcc_options=("5411",),
        supported_currencies=("UYU",),
        amount_ranges={"UYU": (350, 8500)},
        is_online=False,
    ),
    Merchant(
        name="Devoto",
        category="supermarket",
        mcc_options=("5411",),
        supported_currencies=("UYU",),
        amount_ranges={"UYU": (350, 8500)},
        is_online=False,
    ),
    Merchant(
        name="Disco",
        category="supermarket",
        mcc_options=("5411",),
        supported_currencies=("UYU",),
        amount_ranges={"UYU": (350, 8500)},
        is_online=False,
    ),
    Merchant(
        name="Geant",
        category="supermarket",
        mcc_options=("5411",),
        supported_currencies=("UYU",),
        amount_ranges={"UYU": (350, 8500)},
        is_online=False,
    ),
    Merchant(
        name="Ta-Ta",
        category="supermarket",
        mcc_options=("5411",),
        supported_currencies=("UYU",),
        amount_ranges={"UYU": (350, 8500)},
        is_online=False,
    ),
    Merchant(
        name="PedidosYa",
        category="restaurant_delivery",
        mcc_options=("5812", "5814"),
        supported_currencies=("UYU",),
        amount_ranges={"UYU": (400, 3500)},
        is_online=False,
    ),
    Merchant(
        name="Rappi",
        category="restaurant_delivery",
        mcc_options=("5812", "5814"),
        supported_currencies=("UYU",),
        amount_ranges={"UYU": (400, 3500)},
        is_online=False,
    ),
    Merchant(
        name="McDonald's",
        category="restaurant_delivery",
        mcc_options=("5812", "5814"),
        supported_currencies=("UYU",),
        amount_ranges={"UYU": (400, 3500)},
        is_online=False,
    ),
    Merchant(
        name="La Pasiva",
        category="restaurant_delivery",
        mcc_options=("5812", "5814"),
        supported_currencies=("UYU",),
        amount_ranges={"UYU": (400, 3500)},
        is_online=False,
    ),
    Merchant(
        name="Bar Tasende",
        category="restaurant_delivery",
        mcc_options=("5812", "5814"),
        supported_currencies=("UYU",),
        amount_ranges={"UYU": (400, 3500)},
        is_online=False,
    ),
    Merchant(
        name="Netflix",
        category="digital_subscription",
        mcc_options=("4899", "5815"),
        supported_currencies=("USD",),
        amount_ranges={"USD": (4.99, 19.99)},
        is_online=True,
    ),
    Merchant(
        name="Spotify",
        category="digital_subscription",
        mcc_options=("4899", "5815"),
        supported_currencies=("USD",),
        amount_ranges={"USD": (4.99, 19.99)},
        is_online=True,
    ),
    Merchant(
        name="HBO Max",
        category="digital_subscription",
        mcc_options=("4899", "5815"),
        supported_currencies=("USD",),
        amount_ranges={"USD": (4.99, 19.99)},
        is_online=True,
    ),
    Merchant(
        name="Disney+",
        category="digital_subscription",
        mcc_options=("4899", "5815"),
        supported_currencies=("USD",),
        amount_ranges={"USD": (4.99, 19.99)},
        is_online=True,
    ),
    Merchant(
        name="Amazon Prime",
        category="digital_subscription",
        mcc_options=("4899", "5815"),
        supported_currencies=("USD",),
        amount_ranges={"USD": (4.99, 19.99)},
        is_online=True,
    ),
    Merchant(
        name="ChatGPT Plus",
        category="digital_subscription",
        mcc_options=("4899", "5815"),
        supported_currencies=("USD",),
        amount_ranges={"USD": (4.99, 19.99)},
        is_online=True,
    ),
    Merchant(
        name="Uber",
        category="mobility",
        mcc_options=("4121",),
        supported_currencies=("UYU",),
        amount_ranges={"UYU": (150, 900)},
        is_online=False,
    ),
    Merchant(
        name="Cabify",
        category="mobility",
        mcc_options=("4121",),
        supported_currencies=("UYU",),
        amount_ranges={"UYU": (150, 900)},
        is_online=False,
    ),
    Merchant(
        name="Uber Eats",
        category="mobility",
        mcc_options=("4121",),
        supported_currencies=("UYU",),
        amount_ranges={"UYU": (150, 900)},
        is_online=False,
    ),
    Merchant(
        name="Antel",
        category="telecom",
        mcc_options=("4814",),
        supported_currencies=("UYU",),
        amount_ranges={"UYU": (600, 2500)},
        is_online=False,
    ),
    Merchant(
        name="Movistar",
        category="telecom",
        mcc_options=("4814",),
        supported_currencies=("UYU",),
        amount_ranges={"UYU": (600, 2500)},
        is_online=False,
    ),
    Merchant(
        name="MercadoLibre",
        category="ecommerce",
        mcc_options=("5942", "5999"),
        supported_currencies=("UYU", "USD"),
        amount_ranges={"UYU": (800, 12000), "USD": (15, 200)},
        is_online=True,
    ),
    Merchant(
        name="Amazon",
        category="ecommerce",
        mcc_options=("5942", "5999"),
        supported_currencies=("USD",),
        amount_ranges={"USD": (15, 200)},
        is_online=True,
        countries=("US",),
    ),
    Merchant(
        name="AliExpress",
        category="ecommerce",
        mcc_options=("5942", "5999"),
        supported_currencies=("USD",),
        amount_ranges={"USD": (15, 200)},
        is_online=True,
        countries=("CN",),
    ),
    Merchant(
        name="Ancap",
        category="fuel",
        mcc_options=("5541",),
        supported_currencies=("UYU",),
        amount_ranges={"UYU": (1500, 4500)},
        is_online=False,
    ),
    Merchant(
        name="Petrobras",
        category="fuel",
        mcc_options=("5541",),
        supported_currencies=("UYU",),
        amount_ranges={"UYU": (1500, 4500)},
        is_online=False,
    ),
    Merchant(
        name="San Roque",
        category="pharmacy",
        mcc_options=("5912",),
        supported_currencies=("UYU",),
        amount_ranges={"UYU": (250, 2800)},
        is_online=False,
    ),
    Merchant(
        name="Farmashop",
        category="pharmacy",
        mcc_options=("5912",),
        supported_currencies=("UYU",),
        amount_ranges={"UYU": (250, 2800)},
        is_online=False,
    ),
)

MERCHANTS_BY_NAME = {merchant.name: merchant for merchant in MERCHANTS}
MERCHANTS_BY_CURRENCY = {
    "UYU": [merchant for merchant in MERCHANTS if "UYU" in merchant.supported_currencies],
    "USD": [merchant for merchant in MERCHANTS if "USD" in merchant.supported_currencies],
}

MERCHANT_WEIGHTS = {
    "Tienda Inglesa": 9,
    "Uber": 8,
    "Netflix": 7,
    "MercadoLibre": 6,
    "PedidosYa": 5,
}

CITY_BY_COUNTRY = {
    "UY": ("Montevideo", "Canelones", "Maldonado", "Punta del Este", "Colonia"),
    "US": ("Seattle", "Miami", "Austin", "San Francisco"),
    "CN": ("Shenzhen", "Guangzhou", "Shanghai"),
}


def choose_weighted_merchant(currency: str, rng: random.Random) -> Merchant:
    candidates = MERCHANTS_BY_CURRENCY[currency]
    weights = [MERCHANT_WEIGHTS.get(merchant.name, 1) for merchant in candidates]
    return rng.choices(candidates, weights=weights, k=1)[0]


def previous_month_start(anchor: date, months_back: int) -> date:
    year = anchor.year
    month = anchor.month - months_back
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def distributed_timestamps(month_start: date, count: int, rng: random.Random) -> list[datetime]:
    _, last_day = calendar.monthrange(month_start.year, month_start.month)
    day_pool = list(range(1, last_day + 1))
    days: list[int] = []
    while len(days) < count:
        days.extend(day_pool)
    days = days[:count]
    rng.shuffle(days)

    timestamps: list[datetime] = []
    for day in days:
        period = rng.choice(("morning", "afternoon", "night"))
        if period == "morning":
            hour = rng.randint(8, 11)
        elif period == "afternoon":
            hour = rng.randint(12, 17)
        else:
            hour = rng.randint(18, 22)
        minute = rng.randint(0, 59)
        second = rng.randint(0, 59)
        timestamps.append(
            datetime(
                month_start.year,
                month_start.month,
                day,
                hour,
                minute,
                second,
                tzinfo=timezone.utc,
            )
        )
    timestamps.sort()
    return timestamps


def sample_amount(amount_range: tuple[float, float], rng: random.Random) -> float:
    return round(rng.uniform(*amount_range), 2)


def sample_fx_rate(rng: random.Random) -> float:
    return round(rng.uniform(39.0, 43.0), 4)


def sample_country(merchant: Merchant, override: str | None = None) -> str:
    if override:
        return override
    return RNG.choice(merchant.countries)


def sample_city(country: str, rng: random.Random) -> str:
    cities = CITY_BY_COUNTRY.get(country, ("Unknown",))
    return rng.choice(cities)


def sample_postal_code(country: str, rng: random.Random) -> str:
    if country == "UY":
        return str(rng.randint(10000, 99000))
    if country in {"US", "CN"}:
        return str(rng.randint(10000, 99999))
    return str(rng.randint(10000, 99999))


def random_public_ip(rng: random.Random) -> str:
    first = rng.choice((23, 45, 66, 77, 91, 104, 181, 190, 200))
    return f"{first}.{rng.randint(1, 254)}.{rng.randint(1, 254)}.{rng.randint(1, 254)}"


def build_transaction(
    *,
    user_id: str,
    timestamp: datetime,
    currency: str,
    rng: random.Random,
    merchant_name: str | None = None,
    merchant_country_override: str | None = None,
    amount_override: float | None = None,
    tokenized_override: bool | None = None,
) -> dict[str, Any]:
    merchant = (
        MERCHANTS_BY_NAME[merchant_name]
        if merchant_name is not None
        else choose_weighted_merchant(currency, rng)
    )

    if currency not in merchant.supported_currencies:
        raise ValueError(f"Merchant {merchant.name} does not support currency {currency}")

    country = sample_country(merchant, merchant_country_override)
    amount = (
        round(amount_override, 2)
        if amount_override is not None
        else sample_amount(merchant.amount_ranges[currency], rng)
    )
    fx_rate = sample_fx_rate(rng) if currency == "USD" else None

    if merchant.is_online:
        entry_mode = "online"
        card_present = False
        cvm = "none"
    else:
        entry_mode = rng.choices(
            ("contactless", "chip", "manual"), weights=(60, 38, 2), k=1
        )[0]
        card_present = True
        cvm = rng.choice(("pin", "biometric"))

    is_tokenized = (
        tokenized_override
        if tokenized_override is not None
        else (rng.random() < 0.35 if merchant.is_online else rng.random() < 0.05)
    )

    sales_tax: float | None = None
    if currency == "UYU" and country == "UY":
        sales_tax = round(amount * 0.22, 2)

    reference_number = rng.randint(100000, 999999)
    customer_reference = f"REF-{reference_number}" if rng.random() < 0.45 else None
    invoice_number = f"FAC-{rng.randint(10000, 99999)}" if rng.random() < 0.4 else None

    return {
        "user_id": user_id,
        "card_last4": rng.choice(CARD_LAST4_POOL),
        "card_brand": rng.choice(CARD_BRANDS),
        "total_amount": amount,
        "currency": currency,
        "fx_rate": fx_rate,
        "transaction_at": timestamp.isoformat(),
        "merchant_name": merchant.name,
        "merchant_dba": merchant.dba_name,
        "mcc": rng.choice(merchant.mcc_options),
        "card_present": card_present,
        "entry_mode": entry_mode,
        "sales_tax": sales_tax,
        "customer_reference": customer_reference,
        "invoice_number": invoice_number,
        "merchant_postal_code": sample_postal_code(country, rng),
        "merchant_city": sample_city(country, rng),
        "merchant_country": country,
        "terminal_id": (
            f"ECOM-{rng.randint(100000, 999999)}"
            if merchant.is_online
            else f"POS-{rng.randint(10000000, 99999999)}"
        ),
        "ip_address": random_public_ip(rng),
        "is_tokenized": is_tokenized,
        "cvm": cvm,
    }


def month_key(timestamp_iso: str) -> str:
    return timestamp_iso[:7]


def chunked(items: list[dict[str, Any]], chunk_size: int) -> Iterable[list[dict[str, Any]]]:
    for index in range(0, len(items), chunk_size):
        yield items[index : index + chunk_size]


def validate_transactions(rows: list[dict[str, Any]], expected_months: list[str]) -> None:
    if len(rows) != 90:
        raise RuntimeError(f"Expected 90 transactions, got {len(rows)}")

    month_counts = Counter(month_key(row["transaction_at"]) for row in rows)
    for month in expected_months:
        if month_counts[month] != 30:
            raise RuntimeError(f"Month {month} must have 30 transactions, got {month_counts[month]}")

    currency_counts = Counter(row["currency"] for row in rows)
    if currency_counts["UYU"] != 72 or currency_counts["USD"] != 18:
        raise RuntimeError(
            f"Currency mix must be 72 UYU / 18 USD, got {currency_counts['UYU']} / {currency_counts['USD']}"
        )

    merchant_counts = Counter(row["merchant_name"] for row in rows)
    repeated_merchants = [name for name, qty in merchant_counts.items() if qty >= 4]
    if len(repeated_merchants) < 3:
        raise RuntimeError("Need at least 3 merchants repeated 4+ times")

    if not any(row["merchant_country"] == "CN" for row in rows):
        raise RuntimeError("Need at least 1 international transaction in CN")

    if not any(row["is_tokenized"] for row in rows):
        raise RuntimeError("Need at least 1 tokenized transaction")

    has_under_10_usd_equivalent = False
    manual_count = 0
    for row in rows:
        merchant = MERCHANTS_BY_NAME[row["merchant_name"]]
        if merchant.is_online:
            if row["entry_mode"] != "online":
                raise RuntimeError(f"{merchant.name}: online merchants must use entry_mode='online'")
            if row["card_present"] is not False:
                raise RuntimeError(f"{merchant.name}: online merchants must have card_present=false")
            if row["cvm"] != "none":
                raise RuntimeError(f"{merchant.name}: online merchants must have cvm='none'")
        else:
            if row["entry_mode"] not in {"contactless", "chip", "manual"}:
                raise RuntimeError(f"{merchant.name}: invalid entry_mode for in-person transaction")
            if row["card_present"] is not True:
                raise RuntimeError(f"{merchant.name}: in-person merchants must have card_present=true")
            if row["cvm"] not in {"pin", "biometric"}:
                raise RuntimeError(f"{merchant.name}: in-person merchants must have cvm pin/biometric")
            if row["entry_mode"] == "manual":
                manual_count += 1

        if row["currency"] == "USD":
            usd_equivalent = float(row["total_amount"])
        else:
            usd_equivalent = float(row["total_amount"]) / DEFAULT_UYU_PER_USD
        if usd_equivalent < 10:
            has_under_10_usd_equivalent = True

    if not has_under_10_usd_equivalent:
        raise RuntimeError("Need at least 1 transaction below USD 10 equivalent")
    if manual_count > 3:
        raise RuntimeError(f"Manual entry_mode should be rare, got {manual_count}")


def build_seed_rows(user_id: str) -> list[dict[str, Any]]:
    today = datetime.now().date()
    month_starts = [previous_month_start(today.replace(day=1), i) for i in range(3)]
    expected_month_keys = [month.strftime("%Y-%m") for month in month_starts]

    forced_specs = {
        0: [
            {"merchant_name": "Tienda Inglesa", "currency": "UYU"},
            {"merchant_name": "Tienda Inglesa", "currency": "UYU"},
            {"merchant_name": "Tienda Inglesa", "currency": "UYU"},
            {"merchant_name": "Uber", "currency": "UYU"},
            {"merchant_name": "Uber", "currency": "UYU"},
            {"merchant_name": "Netflix", "currency": "USD"},
            {"merchant_name": "Netflix", "currency": "USD"},
            {"merchant_name": "Spotify", "currency": "USD", "amount_override": 7.99},
            {"merchant_name": "ChatGPT Plus", "currency": "USD", "tokenized_override": True},
        ],
        1: [
            {"merchant_name": "Tienda Inglesa", "currency": "UYU"},
            {"merchant_name": "Tienda Inglesa", "currency": "UYU"},
            {"merchant_name": "Tienda Inglesa", "currency": "UYU"},
            {"merchant_name": "Uber", "currency": "UYU"},
            {"merchant_name": "Uber", "currency": "UYU"},
            {"merchant_name": "Netflix", "currency": "USD"},
            {"merchant_name": "Netflix", "currency": "USD"},
            {"merchant_name": "AliExpress", "currency": "USD", "merchant_country_override": "CN"},
        ],
        2: [
            {"merchant_name": "Tienda Inglesa", "currency": "UYU"},
            {"merchant_name": "Tienda Inglesa", "currency": "UYU"},
            {"merchant_name": "Uber", "currency": "UYU"},
            {"merchant_name": "Uber", "currency": "UYU"},
            {"merchant_name": "Uber", "currency": "UYU"},
            {"merchant_name": "Netflix", "currency": "USD"},
            {"merchant_name": "Netflix", "currency": "USD"},
        ],
    }

    rows: list[dict[str, Any]] = []

    for month_index, month_start in enumerate(month_starts):
        timestamps = distributed_timestamps(month_start, 30, RNG)
        month_rows: list[dict[str, Any]] = []

        currency_plan = ["UYU"] * 24 + ["USD"] * 6
        RNG.shuffle(currency_plan)

        specs_for_month = forced_specs[month_index]
        for forced in specs_for_month:
            currency_plan.remove(forced["currency"])
            month_rows.append(
                build_transaction(
                    user_id=user_id,
                    timestamp=timestamps[len(month_rows)],
                    currency=forced["currency"],
                    rng=RNG,
                    merchant_name=forced["merchant_name"],
                    merchant_country_override=forced.get("merchant_country_override"),
                    amount_override=forced.get("amount_override"),
                    tokenized_override=forced.get("tokenized_override"),
                )
            )

        for currency in currency_plan:
            month_rows.append(
                build_transaction(
                    user_id=user_id,
                    timestamp=timestamps[len(month_rows)],
                    currency=currency,
                    rng=RNG,
                )
            )

        if len(month_rows) != 30:
            raise RuntimeError(f"Month index {month_index} generated {len(month_rows)} rows instead of 30")
        rows.extend(month_rows)

    validate_transactions(rows, expected_month_keys)
    return rows


def get_required_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        raise RuntimeError(f"Missing required env var: {var_name}")
    return value


def build_client() -> Client:
    supabase_url = get_required_env("SUPABASE_URL")
    supabase_service_role_key = get_required_env("SUPABASE_SERVICE_ROLE_KEY")
    return create_client(supabase_url, supabase_service_role_key)


def print_summary(rows: list[dict[str, Any]]) -> None:
    merchant_counts = Counter(row["merchant_name"] for row in rows)
    month_counts = Counter(month_key(row["transaction_at"]) for row in rows)
    currency_counts = Counter(row["currency"] for row in rows)

    print("Seed completed successfully.")
    print(f"Inserted transactions: {len(rows)}")
    print(f"Unique merchants: {len(merchant_counts)}")
    print(f"Currency mix: UYU={currency_counts['UYU']} / USD={currency_counts['USD']}")
    print("Transactions by month:")
    for month, count in sorted(month_counts.items(), reverse=True):
        print(f"  - {month}: {count}")
    print("Top 5 merchants:")
    for merchant_name, qty in merchant_counts.most_common(5):
        print(f"  - {merchant_name}: {qty}")


def main() -> None:
    load_dotenv(ENV_PATH)

    demo_user_id = get_required_env("DEMO_USER_ID")
    rows = build_seed_rows(demo_user_id)
    client = build_client()

    # Clear dependent tickets first to avoid FK violations when reseeding.
    client.table("chargeback_tickets").delete().eq("user_id", demo_user_id).execute()
    client.table("transactions").delete().eq("user_id", demo_user_id).execute()
    for chunk in chunked(rows, 30):
        client.table("transactions").insert(chunk).execute()

    print_summary(rows)


if __name__ == "__main__":
    main()
