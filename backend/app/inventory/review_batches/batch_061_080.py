"""Lead-reviewed records 61–80; independent semantic review pending."""

from app.inventory.review_authoring import cash, finance, mileage, record, term
from app.inventory.review_authoring import claim as c

RECORDS = (
    record(
        "61",
        62,
        (
            "Single36999AED amount in concise vehicle advert is asking price;169859km "
            "odometer. USA Space spelling retained as regional claim without further repair."
        ),
        cash("36,999 AED", 3699900),
        mileage("169859 Km", 169859),
        c("regional_specs", "USA Space", "USA stated"),
        c(
            "engine",
            "2500 Cc 4 Cylinder",
            4,
            role="cylinder_count",
            conditions=(term("other", "2500 Cc 4 Cylinder", 2500, unit="cc"),),
        ),
        c("features", "BLUE", "blue exterior", role="color"),
    ),
    record(
        "62",
        63,
        (
            "Japan import/black interior/clean condition explicit; no numeric mileage. "
            "Dealer160auction access is not vehicle evidence."
        ),
        c("regional_specs", "FRESH JAPAN IMPORT", "Japan import", field="title"),
        c("features", "Interior Black", "black interior", role="color"),
        c("condition", "Neat & Clean Car", role="seller_condition"),
        c("mileage_km", "Low Mileage", disposition="ambiguous", reason="No numeric odometer."),
    ),
    record(
        "63",
        64,
        (
            "Title JOINS spelling not used to overwrite structured John Cooper Works. "
            "Recent/full-service wording not complete history. Cash-only insurance is "
            "conditional benefit."
        ),
        c("regional_specs", "GCC", "GCC", field="title"),
        c("features", "PANORAMIC ROOF", field="title"),
        c(
            "service_history",
            "Recently Serviced",
            "recently serviced; full history not established",
            role="recent_service",
        ),
        c(
            "service_history",
            "Full Service",
            "full service performed; full history not established",
            role="service_performed",
        ),
        c("service_plan", "1 Free Service", "1 free service", role="included_benefit"),
        c(
            "features",
            "1 Year Free Insurance (FOR CASH DEALS ONLY)",
            disposition="conditional",
            reason="Cash-deal condition retained; no unconditional insurance inclusion.",
            conditions=(
                term("scope", "1 Year Free Insurance (FOR CASH DEALS ONLY)", "cash deals only"),
            ),
        ),
        c("condition", "Guaranteed Accident Free", role="seller_condition"),
        c("condition", "Single Owner", role="ownership"),
    ),
    record(
        "64",
        65,
        (
            "Literal source4.0 V6 is not corrected from model knowledge; litres not inferred "
            "from bare4.0. Fuel-efficient wording supplies no fuel type. Serviced on time is "
            "not full documented history."
        ),
        c(
            "engine",
            "AUDI Q7 4.0 V6",
            "V6",
            role="configuration",
            conditions=(term("other", "AUDI Q7 4.0 V6", "4.0; unit unstated"),),
        ),
        c("regional_specs", "GCC SPECS", "GCC", field="title"),
        c("features", "7 SEATS", "7 seats", field="title"),
        c("features", "COOLING AND HEATING SEATS", "cooled and heated seats"),
        c("features", "PANORAMIC ROOF KEYLESS START AND KEYLESS ENTRY BLIND SPOT"),
        c("features", "2 ORIGINAL KEYS", "2 original keys"),
        c(
            "condition",
            "NEVER BEEN RESPRAYED BEFORE NEVER HAD ANY MECHANICAL PROBLEMS",
            role="seller_condition",
        ),
        c(
            "service_history",
            "SERVICED ON TIME",
            "serviced on time claimed; full history not established",
        ),
        c(
            "service_history",
            "JUST SERVICED FEW WEEKS AGO",
            "serviced a few weeks before listing; date unstated",
            role="recent_service",
        ),
        c(
            "fuel_type",
            "FUEL EFFICIENT",
            field="title",
            disposition="ambiguous",
            reason="Efficiency marketing does not specify fuel.",
        ),
    ),
    record(
        "65",
        66,
        (
            "71000km and warranty explicitly stated, but warranty has no "
            "provider/terms/current validation. SXT agrees across fields."
        ),
        mileage("71000 KM", 71000),
        c(
            "warranty",
            "Warranty",
            "warranty stated; provider, terms and current validity not established",
        ),
    ),
    record(
        "66",
        67,
        (
            "0km/brand new/Ultimate trim explicit;79999AED cash separate from two monthly5year "
            "plans. Literal V4 retained. First instalment after3months/flexible terms "
            "retained, current warranty not verified."
        ),
        cash("AED 79,999 cash", 7999900),
        finance(
            "AED 1650 monthly for 5 years with 0% Down-Payment / flexible",
            165000,
            down=0,
            years=5,
            flexible=True,
        ),
        finance(
            "AED 1300 monthly for 5 years with 20% Down-Payment / flexible",
            130000,
            down=20,
            years=5,
            flexible=True,
        ),
        c(
            "money",
            "And First Installment After 3 Month",
            "first instalment after3months",
            role="finance_condition",
            disposition="conditional",
            reason="Shared financing offer condition; exact eligibility/scope unstated.",
        ),
        mileage("Odometer : 0 KM", 0),
        c("trim", "Grandland Ultimate", "Ultimate"),
        c("condition", "Brand New", "brand new claimed", field="title", role="newness"),
        c("regional_specs", "Specification : GCC", "GCC"),
        c(
            "warranty",
            "Warranty : Under Agancy Warranty 5 Years",
            "agency warranty5years stated; start/current validity not established",
            conditions=(
                term("duration", "Warranty : Under Agancy Warranty 5 Years", 5, unit="years"),
                term("provider", "Warranty : Under Agancy Warranty 5 Years", "agency unspecified"),
            ),
        ),
        c(
            "engine",
            "Cylinders : V4 1.6L",
            "V4",
            role="configuration",
            conditions=(term("other", "Cylinders : V4 1.6L", "1.6", unit="litres"),),
        ),
    ),
    record(
        "67",
        68,
        (
            "Arabic title/description agree with structured2022 Nissan Patrol Super Safari. No "
            "other extraction-family evidence."
        ),
    ),
    record(
        "68",
        69,
        (
            "34927km odometer separate from30000km conditional free-servicing "
            "limit.2years/free service is offer requiring quote andT&C, not history. Lexus "
            "service history explicit; dealer-wide warranty phrasing not current vehicle coverage."
        ),
        mileage("Mileage 34,927 KM", 34927),
        c("body_type", "LX SUV", "SUV"),
        c(
            "transmission",
            "AT F Sport",
            "automatic",
            field="title",
            reason=(
                "AT is the explicit transmission abbreviation in the vehicle specification "
                "sequence; reviewed interpretation."
            ),
        ),
        c(
            "fuel_type",
            "LX SUV P 3.5L T AT",
            "P",
            disposition="ambiguous",
            reason="Single-letter P is not expanded into fuel without an explicit source "
            "definition.",
        ),
        c("engine", "3.5L", "3.5", field="title", role="displacement", unit="litres"),
        c("regional_specs", "GCC Specs", "GCC"),
        c(
            "service_history",
            "Lexus Service History",
            "Lexus service history stated; completeness unspecified",
        ),
        c(
            "service_plan",
            "2 years Free servicing (up to 30,000 km*)",
            disposition="conditional",
            reason=(
                "Special offer requires quotingDUBIZZLE and sourceT&C; eligibility/current "
                "validity unverified."
            ),
            conditions=(
                term("duration", "2 years Free servicing (up to 30,000 km*)", 2, unit="years"),
                term(
                    "distance_limit", "2 years Free servicing (up to 30,000 km*)", 30000, unit="km"
                ),
                term("scope", "SPECIAL OFFER QUOTE DUBIZZLE", "quoteDUBIZZLE"),
                term("other", "T&C’s apply", "terms apply"),
            ),
        ),
        c(
            "distance",
            "up to 30,000 km*",
            30000,
            role="service_plan_limit",
            unit="km",
            qualifier="at_most",
            disposition="conditional",
            reason="Conditional servicing limit, not odometer.",
        ),
        c(
            "warranty",
            "Lexus Warranty with all Al Futtaim Pre-Owned vehicles",
            subject="dealer",
            disposition="dealer_wide",
            reason=(
                "All-vehicles dealer warranty advertising; listing-specific terms/current "
                "coverage not established."
            ),
        ),
        c("condition", "Excellent Condition", role="seller_condition"),
    ),
    record(
        "69",
        70,
        "GCC/white color explicit; calen is not repaired. No numeric price/mileage.",
        c("regional_specs", "GCC", "GCC", field="title"),
        c("features", "white color", "white exterior", field="title", role="color"),
        c(
            "condition",
            "calen car",
            field="title",
            disposition="ambiguous",
            reason="Unclear spelling not repaired into factual condition.",
        ),
    ),
    record(
        "70",
        71,
        (
            "Japan import/black interior/clean condition explicit; mileage only qualitative. "
            "Dealer biography numbers excluded from vehicle age/mileage."
        ),
        c("regional_specs", "FRESH JAPAN IMPORT", "Japan import", field="title"),
        c("features", "Interior Black", "black interior", role="color"),
        c("condition", "Neat & Clean Car", role="seller_condition"),
        c("mileage_km", "Low Mileage", disposition="ambiguous", reason="No numeric odometer."),
    ),
    record(
        "71",
        72,
        (
            "71000km explicit. Agency warranty/service package stated untilJanuary2027; month "
            "precision and unknown current validity retained. No odometer inferred from expiry."
        ),
        mileage("71000 km", 71000),
        c("regional_specs", "GCC Specs", "GCC"),
        c(
            "engine",
            "3.0L Turbocharged V6",
            "V6",
            role="configuration",
            conditions=(term("other", "3.0L Turbocharged V6", "3.0", unit="litres"),),
        ),
        c(
            "warranty",
            "Agency warranty and service package until January 2027",
            "agency warranty stated untilJanuary2027; current validity unverified",
            conditions=(
                term("expiry", "Agency warranty and service package until January 2027", "2027-01"),
                term(
                    "provider",
                    "Agency warranty and service package until January 2027",
                    "agency unspecified",
                ),
            ),
        ),
        c(
            "service_plan",
            "Agency warranty and service package until January 2027",
            "agency service package stated untilJanuary2027; current validity unverified",
            conditions=(
                term("expiry", "Agency warranty and service package until January 2027", "2027-01"),
            ),
        ),
        c("features", "Grey Exterior with Tan Leather Interior", role="color"),
    ),
    record(
        "72",
        73,
        (
            "13000km/Japanese/V8 biturbo explicit. Bare4.0 has no litres suffix; preserved as "
            "engine descriptor. Mask after grade pending targeted source inspection."
        ),
        mileage("Mileage - 13000 KM", 13000),
        c("regional_specs", "JAPANESE SPECS", "Japanese", field="title"),
        c(
            "engine",
            "V8 BITURBO 4.0 503 HP",
            "V8 biturbo",
            role="configuration",
            conditions=(term("other", "V8 BITURBO 4.0 503 HP", "4.0; unit unstated"),),
        ),
        c("engine", "503 HP", 503, role="power", unit="hp"),
        c(
            "condition",
            "Grade - 4.5 B",
            "grade4.5B stated; grading scheme unstated",
            role="seller_grade",
        ),
        c(
            "condition",
            "Clean Title Scratch Less Car No Paint No Accident",
            role="seller_condition",
        ),
        c("features", "White/Black Interior Panoramic Sunroof"),
        c(
            "features",
            (
                "Lane Assist Radar Adaptive Cruise Control 64 Colour Ambient lights Brumester "
                "Surround Sound System"
            ),
        ),
    ),
    record(
        "73",
        74,
        (
            "45000km/GCC and recentRollsRoyce service explicit. New tyres not new car. "
            "Duplicate dealer warranty/services retained once with occurrence index "
            "and dealer scope."
        ),
        mileage("45,000KM", 45000, field="title"),
        c("regional_specs", "GCC", "GCC", field="title"),
        c(
            "service_history",
            "CAR RECENT SERVICE DONE FROM ROLLS ROYCE",
            "recent service atRollsRoyce claimed",
            role="recent_service",
        ),
        c("features", "CAR HAS 4 BRAND NEW TYRES", "4 new tyres"),
        c("features", "3 BUTTONS | STAR LIGHT", field="title"),
        c(
            "warranty",
            "A warranty can be arranged",
            occurrence=0,
            subject="dealer",
            disposition="conditional",
            reason="Optional dealer service repeated in boilerplate; not included vehicle "
            "warranty.",
        ),
        c(
            "service_plan",
            "A service contract can be arranged",
            occurrence=0,
            subject="dealer",
            disposition="conditional",
            reason="Optional dealer service repeated in boilerplate; not included vehicle plan.",
        ),
    ),
    record(
        "74",
        75,
        (
            "WarrantyDec2026 is a source expiry claim at month precision; no current-validity "
            "assertion. Low mileages qualitative. Dealer400stock count not odometer."
        ),
        c(
            "warranty",
            "WARRANTY DEC 2026",
            "warranty stated untilDecember2026; current validity unverified",
            field="title",
            conditions=(term("expiry", "WARRANTY DEC 2026", "2026-12", field="title"),),
        ),
        c("features", "TWO TONE EXTERIOR", field="title", role="color"),
        c(
            "mileage_km",
            "LOW MILEAGES",
            field="title",
            disposition="ambiguous",
            reason="No numeric odometer.",
        ),
    ),
    record(
        "75",
        76,
        (
            "GCC explicit title. Description is general WranglerSahara model overview; "
            "equipment and engine not promoted to this vehicle's verified configuration."
        ),
        c("regional_specs", "GCC", "GCC", field="title"),
        c(
            "engine",
            "3.6-liter V6 engine (Pentastar) producing 285 horsepower and 260 lb-ft of torque",
            "3.6L V6 model-overview claim",
            subject="unspecified",
            disposition="ambiguous",
            reason=(
                "Generic model-overview specification; this individual car's configuration not "
                "established."
            ),
        ),
        c(
            "features",
            "Dual front airbags, side-curtain airbags, and stability control",
            subject="unspecified",
            disposition="ambiguous",
            reason=(
                "Listed as standard safety in generic model overview; not individual equipment "
                "confirmation."
            ),
        ),
    ),
    record(
        "76",
        77,
        (
            "Hybrid explicitly stated without subtype; clean condition source claim. Full "
            "options not specific equipment."
        ),
        c("fuel_type", "hybrid", "hybrid", field="title"),
        c("condition", "very clean car outside and inside", field="title", role="seller_condition"),
        c(
            "features",
            "full options",
            field="title",
            disposition="ambiguous",
            reason="No specific equipment listed.",
        ),
    ),
    record(
        "77",
        78,
        (
            "98000km/USA and literal V4 explicit; no I4 correction. Digital kilometre meter is "
            "equipment, not a second odometer value. Quottro not silently standardized."
        ),
        mileage("98000 km", 98000),
        c("regional_specs", "Usa Specification", "USA"),
        c("engine", "V4", "V4", field="title", role="configuration"),
        c("condition", "Clean car", role="seller_condition"),
        c("features", "Sunroof Digital kilometer meter Reverse camera Parking sensor"),
    ),
    record(
        "78",
        79,
        (
            "Arabic advert offers instalments with ten-thousand down payment but no currency. "
            "Amount never becomes AED/cash asking price."
        ),
        c(
            "money",
            "دفعة عشرة الاف",
            10000,
            role="down_payment",
            unit="currency_unknown",
            disposition="conditional",
            reason="Arabic ten-thousand down-payment offer; currency and eligibility unstated.",
        ),
    ),
    record(
        "79",
        80,
        (
            "73000km distinct from historical85k service cost without currency. Full history "
            "asserted;GT trim/W12/6.0L explicit. Tyres new, car not claimed new."
        ),
        mileage("73000kms", 73000),
        c("trim", "Continental GT", "GT", field="title"),
        c("regional_specs", "GCC SPECS", "GCC"),
        c(
            "engine",
            "6.0L W12",
            "W12",
            field="title",
            role="configuration",
            conditions=(term("other", "6.0L W12", "6.0", unit="litres", field="title"),),
        ),
        c("service_history", "FULL SERVICE HISTORY", "full service history", field="title"),
        c(
            "service_history",
            "Full agency services at Bentley",
            "full agency services atBentley",
            role="provider_history",
        ),
        c(
            "money",
            "last major service done at agency cost 85k",
            85000,
            role="historical_service_cost",
            unit="currency_unknown",
            disposition="ambiguous",
            reason="Historical service cost without currency, never cash vehicle price.",
        ),
        c("condition", "Accident free", role="seller_condition"),
        c("features", "new suspensions included", role="recent_replacements"),
        c("features", "Brand new tyres", role="recent_replacements"),
    ),
    record(
        "80",
        81,
        (
            "11000km/GCC/gray explicit. Warranty available is conditional offer without "
            "established inclusion/current coverage."
        ),
        mileage("11,000 KM", 11000, field="title"),
        c("regional_specs", "GCC", "GCC", field="title"),
        c("features", "GRAY COLOR", "gray exterior", field="title", role="color"),
        c(
            "warranty",
            "WARRANTY AVAILABLE",
            field="title",
            disposition="conditional",
            reason="Availability does not establish included/current warranty.",
        ),
    ),
)
