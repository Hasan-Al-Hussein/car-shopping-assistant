"""Lead-reviewed records 41–60; independent semantic review pending."""

from app.inventory.review_authoring import cash, finance, mileage, record, term
from app.inventory.review_authoring import claim as c

RECORDS = (
    record(
        "41",
        42,
        (
            "FSH explicitly asserted; original KM gives no numeric odometer. Dubai "
            "registration is not vehicle location. Seller negates faults/accidents/flood, "
            "without verification."
        ),
        c("regional_specs", "GCC Specs", "GCC"),
        c("service_history", "FSH", "full service history claimed"),
        c(
            "location",
            "Dubai Registration",
            "Dubai registration",
            disposition="ambiguous",
            reason="Registration jurisdiction does not establish current vehicle location.",
        ),
        c(
            "mileage_km",
            "Original KM",
            field="title",
            disposition="ambiguous",
            reason="No numeric odometer.",
        ),
        c("condition", "No faults, No accidents, No Flood", role="seller_condition"),
        c("condition", "1 Owner Original Paint", role="seller_condition"),
        c("features", "4x4 Dubai Registration 2 Original Keys", "4x4; two original keys"),
        c("features", "Screen with reverse Camera"),
    ),
    record(
        "42",
        43,
        (
            "23900km odometer distinct from23895km service event. Dated AGMC service and2028 "
            "contract expiry are historical source claims; no current validity inferred."
        ),
        mileage("Mileage: 23,900 Kms", 23900),
        c("regional_specs", "Spec: GCC", "GCC"),
        c(
            "service_history",
            "Last Service: 18/05/2026 or 23,895 Kms (AGMC)",
            "last service stated18/05/2026 or23895km atAGMC",
            role="service_event",
        ),
        c(
            "distance",
            "Last Service: 18/05/2026 or 23,895 Kms (AGMC)",
            23895,
            role="service_event_mileage",
            unit="km",
        ),
        c(
            "service_plan",
            "Next Service: 18/05/2027",
            "next service stated18/05/2027",
            role="service_due",
        ),
        c(
            "service_plan",
            "Service Contract: 28/08/2028 (AGMC)",
            "AGMC service contract stated until28/08/2028; current validity unverified",
            conditions=(
                term("expiry", "Service Contract: 28/08/2028 (AGMC)", "2028-08-28"),
                term("provider", "Service Contract: 28/08/2028 (AGMC)", "AGMC"),
            ),
        ),
        c("features", "4 buttons starlights!", field="title"),
    ),
    record(
        "43",
        44,
        (
            "Explicit GCC, seller condition, leather/electric seats and sunroof. No "
            "odometer/price inferred."
        ),
        c("regional_specs", "G.C.C", "GCC", field="title"),
        c("condition", "IN EXCELLENT CONDITION", field="title", role="seller_condition"),
        c("features", "leather seats,electric seats,sunroof"),
    ),
    record(
        "44",
        45,
        (
            "159750AED cash versus two5year monthly plans;102000km odometer. "
            "Petrol/SUV/automatic explicit. Available warranty is conditional, not established "
            "inclusion/current coverage."
        ),
        cash("AED 159,750.00 in cash", 15975000),
        finance("AED 2,816.00 monthly for 5 years with 10% Down-Payment", 281600, down=10, years=5),
        finance("AED 2,503.00 monthly for 5 years with 20% Down-Payment", 250300, down=20, years=5),
        mileage("Mileage: 102,000 km", 102000),
        c("fuel_type", "V6 petrol engine", "petrol"),
        c(
            "engine",
            "3.0 L V6 petrol engine",
            "V6",
            role="configuration",
            conditions=(term("other", "3.0 L V6 petrol engine", "3.0", unit="litres"),),
        ),
        c("body_type", "this SUV ensures", "SUV"),
        c(
            "transmission",
            "Transmission: 8-speed Automatic AWD",
            "automatic",
            conditions=(term("other", "Transmission: 8-speed Automatic AWD", 8, unit="gears"),),
        ),
        c("regional_specs", "This GCC spec vehicle", "GCC"),
        c(
            "warranty",
            "With warranty and flexible down-payment options available",
            disposition="conditional",
            reason="Warranty availability/terms unspecified; no included/current coverage "
            "assertion.",
        ),
        c("condition", "Condition: Good", "good claimed", role="seller_condition"),
        c("features", "Seating Capacity: 5", "5 seats"),
        c("features", "Rim Size: 16″", "16 inch rims"),
    ),
    record(
        "45",
        46,
        (
            "One-year warranty explicitly stated, with start/provider/current validity "
            "unstated. Full options not expanded."
        ),
        c(
            "warranty",
            "1 year warranty",
            "1 year warranty stated; start/provider/current validity not established",
            conditions=(term("duration", "1 year warranty", 1, unit="years"),),
        ),
        c("condition", "Very good condition", role="seller_condition"),
        c(
            "features",
            "Full options",
            disposition="ambiguous",
            reason="No specific equipment stated.",
        ),
    ),
    record(
        "46",
        47,
        (
            "12000km, roadster and GCC explicit. Optional warranty/service arrangement is "
            "dealer-wide service, not included vehicle coverage/history."
        ),
        mileage("12,000km", 12000, field="title"),
        c("body_type", "ROADSTER", "roadster", field="title"),
        c("regional_specs", "GCC", "GCC", field="title"),
        c(
            "warranty",
            "A warranty can be arranged",
            disposition="conditional",
            subject="dealer",
            reason="Optional dealer arrangement, not established vehicle warranty.",
        ),
        c(
            "service_plan",
            "A service contract can be arranged",
            disposition="conditional",
            subject="dealer",
            reason="Optional dealer arrangement, not included service contract/history.",
        ),
    ),
    record(
        "47",
        48,
        (
            "122090km odometer distinct from104700km last-service and114700km next-service "
            "thresholds. Past due dates do not establish current servicing or warranty."
        ),
        mileage("Mileage: 122,090 Kms", 122090),
        c("regional_specs", "Spec: GCC", "GCC"),
        c(
            "service_history",
            "Last Service: 22/08/2023 or 104,700 Kms (ABD)",
            "last service stated22/08/2023 or104700km atABD",
            role="service_event",
        ),
        c(
            "distance",
            "Last Service: 22/08/2023 or 104,700 Kms (ABD)",
            104700,
            role="service_event_mileage",
            unit="km",
        ),
        c("service_plan", "Next Service: 22/08/2024 or 114,700 Kms", role="service_due"),
        c(
            "distance",
            "Next Service: 22/08/2024 or 114,700 Kms",
            114700,
            role="service_due_mileage",
            unit="km",
            conditions=(
                term(
                    "temporal",
                    "Next Service: 22/08/2024 or 114,700 Kms",
                    "or2024-08-22; source due date",
                ),
            ),
        ),
    ),
    record(
        "48",
        49,
        (
            "Short text supplies white color/GCC. Calen remains ambiguous spelling, not "
            "repaired into clean condition."
        ),
        c("regional_specs", "GCC", "GCC", field="title"),
        c("features", "white color", "white exterior", field="title", role="color"),
        c(
            "condition",
            "Calen car",
            field="title",
            disposition="ambiguous",
            reason="Unclear spelling retained without semantic correction.",
        ),
    ),
    record(
        "49",
        50,
        (
            "500km odometer/Ultimae/roadster/GCC explicit. General-model specifications and "
            "color/customization possibilities withheld as individual-car facts. Performance "
            "speeds not mileage."
        ),
        mileage("500 KM ONLY", 500, field="title"),
        c("trim", "ULTIMAE", "Ultimae", field="title"),
        c("body_type", "ROADSTER", "roadster", field="title"),
        c("regional_specs", "GCC", "GCC", field="title"),
        c(
            "engine",
            "Engine Type: 6.5-liter V12",
            "V12",
            role="configuration",
            subject="unspecified",
            disposition="ambiguous",
            reason="Generic model overview, not individual vehicle configuration confirmation.",
            conditions=(term("other", "Engine Type: 6.5-liter V12", "6.5", unit="litres"),),
        ),
        c(
            "transmission",
            "7-speed ISR (Independent Shifting Rod) automated manual transmission",
            "automated manual",
            subject="unspecified",
            disposition="ambiguous",
            reason="Generic model overview, not individual vehicle transmission confirmation.",
            conditions=(
                term(
                    "other",
                    "7-speed ISR (Independent Shifting Rod) automated manual transmission",
                    7,
                    unit="gears",
                ),
            ),
        ),
        c(
            "features",
            "Drivetrain: All-wheel drive (AWD)",
            "AWD",
            role="drivetrain",
            subject="unspecified",
            disposition="ambiguous",
            reason="Generic model overview, not individual vehicle equipment confirmation.",
        ),
        c(
            "features",
            "The car is available in a variety of striking colors",
            disposition="ambiguous",
            reason="General color possibilities do not identify this car's color.",
        ),
        c(
            "distance",
            "Top Speed: Around 221 mph (356 km/h)",
            "221 mph /356kmh",
            role="performance_speed",
            qualifier="approximate",
            disposition="excluded",
            reason="Performance speed, not odometer.",
        ),
    ),
    record(
        "50",
        51,
        (
            "Japan import/V6/black interior/clean condition explicit; low mileage is "
            "qualitative. Dealer160auctions and years of experience not vehicle facts."
        ),
        c("regional_specs", "FRESH JAPAN IMPORT", "Japan import", field="title"),
        c("engine", "V6", "V6", field="title", role="configuration"),
        c("features", "Black Interior", "black interior", role="color"),
        c("condition", "Neat & Clean Car", role="seller_condition"),
        c("mileage_km", "Low Mileage", disposition="ambiguous", reason="No numeric odometer."),
    ),
    record(
        "51",
        52,
        (
            "Japan import/black interior/clean condition explicit; low mileage is qualitative. "
            "Repeated dealer history unrelated to car age or mileage."
        ),
        c("regional_specs", "JAPAN IMPORT", "Japan import", field="title"),
        c("features", "Black Interior", "black interior", role="color"),
        c("condition", "Neat & Clean Car", role="seller_condition"),
        c("mileage_km", "Low Mileage", disposition="ambiguous", reason="No numeric odometer."),
    ),
    record(
        "52",
        53,
        (
            "Structured2015 conflicts with title/description2014. Both model years survive; no "
            "preferred source. Qualitative low mileage not numeric."
        ),
        c("year", "2014", 2014, field="title", role="model_year"),
        c("year", "Year Of the Model - 2014", 2014, role="model_year"),
        c("regional_specs", "FRESH JAPAN IMPORT", "Japan import", field="title"),
        c("features", "Black Interior • Dynamic Seats • Cooling Seats"),
        c("condition", "Neat & Clean Car", role="seller_condition"),
        c("mileage_km", "Low Mileage", disposition="ambiguous", reason="No numeric odometer."),
    ),
    record(
        "53",
        54,
        (
            "Structured/title model year agree. Japan import/black interior/clean condition "
            "explicit; low mileage cannot become odometer."
        ),
        c("regional_specs", "FRESH JAPAN IMPORT", "Japan import", field="title"),
        c("features", "Interior Black", "black interior", role="color"),
        c("condition", "Neat & Clean Car", role="seller_condition"),
        c("mileage_km", "Low Mileage", disposition="ambiguous", reason="No numeric odometer."),
    ),
    record(
        "54",
        55,
        (
            "0km and brand-new explicitly stated. Warranty5years or150k preserves "
            "disjunction;150k lacks explicit distance unit so not silently km or odometer. No "
            "finance amount."
        ),
        mileage("0KM", 0, field="title"),
        c("condition", "Brand New", "brand new claimed", role="newness"),
        c(
            "warranty",
            "warranty 5 years or 150k",
            "warranty5years or150k; second unit/start/current validity unstated",
            conditions=(
                term("duration", "warranty 5 years or 150k", 5, unit="years"),
                term("other", "warranty 5 years or 150k", "or150k; unit unstated"),
            ),
        ),
        c(
            "distance",
            "150k",
            150000,
            role="warranty_limit",
            disposition="ambiguous",
            reason="Warranty limit lacks explicit distance unit; not odometer.",
        ),
        c("engine", "1.6L", "1.6", role="displacement", unit="litres"),
        c("features", "7 Seats", "7 seats", field="title"),
        c("features", "Silver Color", "silver exterior", field="title", role="color"),
    ),
    record(
        "55",
        56,
        (
            "Japan import/beige interior/clean condition explicit; qualitative mileage "
            "unavailable numerically. Dealer years/contact figures excluded by scope."
        ),
        c("regional_specs", "FRESH JAPAN IMPORT", "Japan import", field="title"),
        c("features", "Interior Beige", "beige interior", role="color"),
        c("condition", "Neat & Clean Car", role="seller_condition"),
        c("mileage_km", "Low Mileage", disposition="ambiguous", reason="No numeric odometer."),
    ),
    record(
        "56",
        57,
        (
            "27000km/Korean specs and two keys explicit. Does not need a dirham is condition "
            "idiom, not zero asking price. Dealer4MATIC name not drivetrain."
        ),
        mileage("Only 27000 KM", 27000),
        c("regional_specs", "Korean specifications", "Korean"),
        c("features", "Two agency keys", "2 agency keys"),
        c(
            "condition",
            "Completely free of paint, accidents and scratches",
            role="seller_condition",
        ),
        c(
            "money",
            "does not need a dirham",
            disposition="excluded",
            role="unclassified_amount",
            reason="Condition idiom, not a money amount or cash asking price.",
        ),
    ),
    record(
        "57",
        58,
        (
            "Pre-owned/like-brand-new distinguished; explicit vehicle availability atDubai "
            "address. Coupe describes comparison model; do not assign coupe body. "
            "Finance0%down is dealer service/conditional."
        ),
        c("condition", "Pre-owned", "pre-owned", role="newness"),
        c("condition", "the car like brand new", role="seller_condition"),
        c(
            "engine",
            "McLaren's twin-turbo V8",
            "V8",
            role="configuration",
            subject="unspecified",
            disposition="ambiguous",
            reason=(
                "Comparative model-overview prose; individual configuration not independently "
                "identified."
            ),
        ),
        c(
            "body_type",
            "open-top driving",
            "open-top",
            subject="unspecified",
            disposition="ambiguous",
            reason="Comparative model-overview prose, not explicit individual-car body "
            "classification.",
        ),
        c(
            "location",
            (
                "Car available in Dubai Sheikh Zayed Road (Luxury Lounge L.L.C, AC01 Building "
                "Shop No.3, Al Quoz Branch Building)"
            ),
            "Dubai Sheikh Zayed Road; Luxury Lounge Al Quoz branch",
        ),
        c("features", "Yellow exterior and black interior", role="color"),
        c(
            "features",
            (
                "CARBON EXTERIOR & INTERIOR - Carbon Ceramic Brakes & Yellow Brake Pads - "
                "20/21 Inch Wheels from (1221)"
            ),
        ),
        c(
            "features",
            (
                "Keyless Start - Front Lift System - Drive Mode - PDC Front and Rear Camera - "
                "Auto LED Headlights - Auto Climate Control"
            ),
        ),
        c(
            "money",
            "Finance options available on leading Bank with competitive rates and 0% down payment",
            0,
            role="down_payment",
            unit="percent",
            subject="dealer",
            disposition="conditional",
            reason="Optional bank finance service, not unconditional eligibility.",
        ),
    ),
    record(
        "58",
        59,
        (
            "58465km explicit. LOCATION follows sales contact block and is retained as dealer "
            "address, not definitive car location. Engine6.75L V8 and seller condition explicit."
        ),
        mileage("58,465 KMs", 58465),
        c(
            "engine",
            "6.75L V8",
            "V8",
            field="title",
            role="configuration",
            conditions=(term("other", "6.75L V8", "6.75", unit="litres", field="title"),),
        ),
        c("condition", "Perfect Condition", field="title", role="seller_condition"),
        c(
            "location",
            "LOCATION: Sheikh Zayed Road, Exit 45 Beside Oasis Center Al Quoz 1, Dubai UAE",
            subject="dealer",
            disposition="dealer_wide",
            reason="Address in showroom sales-contact block, not separate vehicle-location "
            "assertion.",
        ),
    ),
    record(
        "59",
        60,
        (
            "GCC and seller-clean condition explicit. Panorama/4weal spelling not expanded "
            "into exact roof/drivetrain claims; like new is not brand-new."
        ),
        c("regional_specs", "GCC", "GCC", field="title"),
        c("condition", "Very clean", role="seller_condition"),
        c(
            "condition",
            "Like new",
            role="newness",
            disposition="ambiguous",
            reason="Like-new condition does not establish brand-new vehicle.",
        ),
        c(
            "features",
            "Panorama 4 weal",
            disposition="ambiguous",
            reason="Abbreviated/unclear equipment wording retained without repair.",
        ),
    ),
    record(
        "60",
        61,
        (
            "32000AED asking price and36000km explicit.2.0L4cyl andAmerican specs "
            "source-bound. Registration/insurance/bank assistance are dealer services."
        ),
        cash("Price # 32000 Aed", 3200000),
        mileage("36000 km", 36000),
        c("regional_specs", "American Spec", "American"),
        c(
            "engine",
            "2.0L-4 Cyl",
            4,
            field="title",
            role="cylinder_count",
            conditions=(term("other", "2.0L-4 Cyl", "2.0", unit="litres", field="title"),),
        ),
        c("condition", "Excellent Condition", field="title", role="seller_condition"),
    ),
)
