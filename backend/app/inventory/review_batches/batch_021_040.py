"""Lead-reviewed records 21–40; independent semantic review pending."""

from app.inventory.review_authoring import cash, finance, mileage, record, term
from app.inventory.review_authoring import claim as c

RECORDS = (
    record(
        "21",
        22,
        (
            "Explicit petrol, SUV, automatic and142774 km; repeated odometer wording agrees. "
            "Clean title/accident-free remain seller claims. No asking price."
        ),
        c("fuel_type", "Petrol", "petrol", field="title"),
        c("engine", "3.7L Petrol", "3.7", field="title", role="displacement", unit="litres"),
        mileage("With only 142,774 km", 142774),
        c("body_type", "this stylish SUV", "SUV"),
        c("transmission", "Fully Automatic Transmission", "automatic"),
        c("regional_specs", "Import From Japan", "Japan import", field="title"),
        c("condition", "Clean Title & No Accident", role="seller_condition"),
        c("features", "Black Exterior / Black Interior", "black exterior; black interior"),
    ),
    record(
        "22",
        23,
        (
            "Timeless package states2year unlimited-km warranty and2year service contract "
            "with16000km/1year interval. Neither interval nor certified-mileage wording "
            "supplies odometer. Numeric trim707 retained."
        ),
        c(
            "warranty",
            "2 YEAR WARRANTY UNLIMITED KM",
            "2 year warranty; unlimited km; start/current validity not established",
            conditions=(
                term("duration", "2 YEAR WARRANTY UNLIMITED KM", 2, unit="years"),
                term("distance_limit", "2 YEAR WARRANTY UNLIMITED KM", "unlimited", unit="km"),
            ),
        ),
        c(
            "service_plan",
            "2 YEAR SERVICE CONTRACT (16000 Km or 1 year, whichever comes first)",
            conditions=(
                term(
                    "duration",
                    "2 YEAR SERVICE CONTRACT (16000 Km or 1 year, whichever comes first)",
                    2,
                    unit="years",
                ),
                term(
                    "other",
                    "16000 Km or 1 year, whichever comes first",
                    "16000 km or 1 year, whichever first",
                ),
            ),
        ),
        c(
            "distance",
            "16000 Km or 1 year, whichever comes first",
            16000,
            role="service_interval",
            unit="km",
            conditions=(
                term(
                    "temporal",
                    "16000 Km or 1 year, whichever comes first",
                    "or1year, whichever comes first",
                ),
            ),
        ),
        c(
            "service_history",
            "SERVICING COMPLETED",
            "servicing completed; completeness of history not established",
        ),
        c("condition", "CERTIFIED HISTORY AND MILEAGE", role="seller_certification"),
        c("condition", "CERTIFIED PRE-OWNED PACKAGE", "pre-owned", role="newness"),
        c("features", "12 MONTHS OF ROADSIDE ASSISTANCE", role="included_benefit"),
    ),
    record(
        "23",
        24,
        (
            "Arabic description says no maintenance or repair needed; this is condition, not "
            "complete service history. In-showroom instalment offer has no cash figure/currency."
        ),
        c("engine", "2.5 L", "2.5", field="title", role="displacement", unit="litres"),
        c("features", "AWD", "AWD", field="title", role="drivetrain"),
        c(
            "condition",
            "لاتحتاج إلى اي صيانة ولا اصلاح",
            "seller says no maintenance or repair needed",
            role="seller_condition",
        ),
    ),
    record(
        "24",
        25,
        (
            "Full agency service asserted; very low mileage is qualitative and cannot become "
            "numeric odometer. Like-new condition does not mean new vehicle."
        ),
        c("regional_specs", "GCC", "GCC", field="title"),
        c("service_history", "full agency service", "full agency service claimed"),
        c(
            "mileage_km",
            "very low mileage",
            disposition="ambiguous",
            reason="Qualitative mileage without numeric odometer.",
        ),
        c("condition", "original paint single owner", role="seller_condition"),
        c("condition", "no have any accident", "no accident claimed", role="seller_condition"),
        c(
            "condition",
            "like new condition",
            role="newness",
            disposition="ambiguous",
            reason="Like-new appearance is not new-vehicle status.",
        ),
        c("features", "2 keys", "2 keys"),
    ),
    record(
        "25",
        26,
        (
            "Explicit full agency servicing and recent BMW AGMC major service. No numeric "
            "mileage, fuel or asking price. General fully-loaded claim is not expanded."
        ),
        c("service_history", "Fully serviced at agency", "fully serviced at agency"),
        c(
            "service_history",
            "Newly major service done at bmw AGMC",
            "recent major service at BMW AGMC",
            role="recent_service",
        ),
        c("engine", "4.4L", "4.4", field="title", role="displacement", unit="litres"),
        c("engine", "567 HP", 567, field="title", role="power", unit="hp"),
        c("condition", "No accidents , no repaints", role="seller_condition"),
        c(
            "features",
            "new shocks , new brake discs , new brake pads chnaged",
            role="recent_replacements",
        ),
        c(
            "features",
            (
                "CarPlay and touch screen 5 cameras lane departure assistant radar , Anti "
                "collision system Adaptive cruise control Moving object detection system"
            ),
        ),
    ),
    record(
        "26",
        27,
        (
            "Title explicitly SUV/Korea; Arabic equipment and excellent-condition statements "
            "retained. Funding possibilities are conditional. Panamera Motors address is "
            "dealer context."
        ),
        c("body_type", "SUV", "SUV", field="title"),
        c("regional_specs", "korea specs", "Korea", field="title"),
        c(
            "condition",
            "السيارة بحالة ممتازة",
            "vehicle in excellent condition claimed",
            role="seller_condition",
        ),
        c("features", "كراسي مساج- كراسي تبريد وتسخين", "massage seats; cooled and heated seats"),
        c("features", "كاميرا 360", "360 camera"),
        c(
            "money",
            "امكانية تمويل بدون دفعة اولى",
            0,
            role="down_payment",
            unit="percent",
            disposition="conditional",
            reason="Possibility of financing without first payment; eligibility not established.",
        ),
        c(
            "location",
            "Panamera motors ‏‎شارع رقم 5 - الشَّامْخَة - أبو ظبي",
            "Panamera Motors, Al Shamkha, Abu Dhabi",
            subject="dealer",
            disposition="dealer_wide",
            reason="Dealer contact address, not separately stated vehicle location.",
        ),
    ),
    record(
        "27",
        28,
        (
            "Partial history in title conflicts with full history in description. "
            "Explicit75500km andGLC250 trim; narrative conflicts remain unresolved."
        ),
        c("trim", "GLC 250", "GLC 250", field="title"),
        c("body_type", "Coupe", "coupe", field="title"),
        c("regional_specs", "GCC", "GCC", field="title"),
        mileage("75500 km", 75500),
        c(
            "service_history",
            "Partial Service History",
            "partial service history",
            field="title",
            role="history_completeness",
        ),
        c(
            "service_history",
            "Full Service History",
            "full service history",
            role="history_completeness",
        ),
        c(
            "engine",
            "2.0T 4 Cylinder",
            4,
            role="cylinder_count",
            conditions=(term("other", "2.0T 4 Cylinder", "2.0T"),),
        ),
        c("features", "Silver exterior with Red Leather Interior"),
    ),
    record(
        "28",
        29,
        (
            "Title explicitly0km; zero is preserved. No new-status, cash, transmission or "
            "warranty inference from model year/zero mileage."
        ),
        mileage("0km", 0, field="title"),
        c("condition", "Perfect inside and outside", role="seller_condition"),
    ),
    record(
        "29",
        30,
        (
            "From1099Pm lacks stated currency and is a lower-bound finance offer, not cash. "
            "Title warranty offer distinct from dealer-wide1year promise; no current coverage "
            "inferred."
        ),
        c(
            "money",
            "From 1099 Pm",
            1099,
            field="title",
            role="finance_instalment",
            basis="monthly_finance",
            unit="currency_unknown",
            qualifier="at_least",
            disposition="conditional",
            reason="From monthly offer with unstated currency/eligibility; cannot become cash "
            "or AED.",
        ),
        c(
            "warranty",
            "Free Manufacturer Warranty",
            "manufacturer warranty offered; unknown terms apply",
            field="title",
            disposition="conditional",
            reason="Source offer subject to unspecifiedT&C, no unconditional/current coverage.",
            conditions=(term("other", "T&C apply", "unspecified terms apply"),),
        ),
        c(
            "warranty",
            "all our cars come with 1 year’s warranty",
            subject="dealer",
            disposition="dealer_wide",
            reason="Dealer-wide advertising is kept distinct from listing-specific "
            "manufacturer warranty.",
        ),
        c(
            "money",
            "Prices Includes 5 % VAT",
            5,
            role="tax_rate",
            unit="percent",
            subject="dealer",
            disposition="dealer_wide",
            reason="General VAT pricing statement; no vehicle cash amount.",
        ),
    ),
    record(
        "30",
        31,
        (
            "Title supplies specific interior equipment but only qualitative low mileage. "
            "Dealer stock count400 and showroom invitation do not establish odometer/location."
        ),
        c("features", "STARLIGHT | TWO TONE INTERIOR | WOOD TRIM INTERIOR", field="title"),
        c(
            "mileage_km",
            "LOW MILEAGE",
            field="title",
            disposition="ambiguous",
            reason="No numeric mileage stated.",
        ),
    ),
    record(
        "31",
        32,
        (
            "Structured R-Sport versus title F sport remains an unresolved trim conflict; no "
            "correction based on manufacturer knowledge. Arabic seller condition explicit."
        ),
        c("trim", "F sport", "F sport", field="title"),
        c("regional_specs", "GCC", "GCC", field="title"),
        c(
            "condition",
            "بحالة ممتازة جدا",
            "very excellent condition claimed",
            role="seller_condition",
        ),
    ),
    record(
        "32",
        33,
        (
            "Cash70000AED and two4year financing offers separate;100271km odometer. Warranty "
            "third-party3year and title2027 expiry both retained without assuming current "
            "coverage/start.25T AWD does not contradict Prestige equipment trim."
        ),
        cash("AED 70,000 cash", 7000000),
        finance(
            "AED 1,750 monthly for 4 years with 0% Down-Payment / flexible",
            175000,
            down=0,
            years=4,
            flexible=True,
        ),
        finance(
            "AED 1,400 monthly for 4 years with 20% Down-Payment / flexible",
            140000,
            down=20,
            years=4,
            flexible=True,
        ),
        c(
            "money",
            "And First Installment After 3 Month",
            "first instalment after3months",
            role="finance_condition",
            disposition="conditional",
            reason="Financing context supplies deferral; exact offer "
            "applicability/eligibility unstated.",
        ),
        c(
            "features",
            "Free Insurance + Registration",
            field="title",
            disposition="conditional",
            reason="Offer inclusion and eligibility/terms unspecified.",
        ),
        mileage("Odometer : 100,271 Kms", 100271),
        c("regional_specs", "Specification : GCC", "GCC"),
        c(
            "warranty",
            "Warranty : 3rd Party (3 Years)",
            "third-party warranty, 3 years; current validity not established",
            conditions=(
                term("duration", "Warranty : 3rd Party (3 Years)", 3, unit="years"),
                term("provider", "Warranty : 3rd Party (3 Years)", "third party"),
            ),
        ),
        c(
            "warranty",
            "Warranty Till 2027",
            "stated expiry2027; current validity not established",
            field="title",
            role="expiry_statement",
            conditions=(term("expiry", "Warranty Till 2027", "2027", field="title"),),
        ),
        c(
            "engine",
            "Cylinders : V4 2.0L",
            "V4",
            role="configuration",
            conditions=(term("other", "Cylinders : V4 2.0L", "2.0", unit="litres"),),
        ),
        c("features", "Jaguar F-Pace 25T AWD", "25T AWD advertised", role="advertised_variant"),
    ),
    record(
        "33",
        34,
        (
            "Brandnew condition is explicitly paired with Pre-Owned; retain used status and "
            "withhold brand-new interpretation. Fully loaded lacks definite equipment."
        ),
        c("condition", "Pre-Owned", "pre-owned", role="newness"),
        c("condition", "Brandnew condition", role="seller_condition"),
        c("features", "Fully loaded", disposition="ambiguous", reason="No exact equipment stated."),
    ),
    record(
        "34",
        35,
        (
            "4000km and standalone Fully Automatic are listing claims. STATION is retained as "
            "advertised style without a guessed taxonomy. Dealer Japanese-stock narrative is "
            "not per-car origin proof."
        ),
        mileage("Only 4,000Km", 4000),
        c("transmission", "Fully Automatic", "automatic"),
        c("body_type", "STATION", "station", field="title"),
        c("condition", "Clean Title and No Accident", role="seller_condition"),
        c("features", "Audio Control On The Steering Wheel •Climate Control •Fog Lamps"),
        c(
            "regional_specs",
            "Over 100 luxury Japanese Imported cars",
            "Japanese imports",
            subject="dealer",
            disposition="dealer_wide",
            reason="Dealer stock description, not explicit origin of this listing.",
        ),
    ),
    record(
        "35",
        36,
        (
            "Arabic title agrees with structured2017 MINI Cooper S; description is "
            "placeholder. No other fact family stated."
        ),
    ),
    record(
        "36",
        37,
        (
            "G63 specified while structured trim is uninformative Other. URBAN is advertised "
            "customization; fully-options not expanded."
        ),
        c("trim", "G63", "G63", field="title"),
        c("features", "URBAN", "URBAN", field="title", role="advertised_customization"),
        c("condition", "EXCELLENT CONDITION", field="title", role="seller_condition"),
    ),
    record(
        "37",
        38,
        (
            "Explicit V6, regularly serviced, new tires and two keys. Chassis identifier is "
            "not price/odometer; no body type inferred fromVIN."
        ),
        c("engine", "V6", "V6", field="title", role="configuration"),
        c(
            "service_history",
            "Regularly serviced",
            "regularly serviced claimed; documentation/completeness unstated",
        ),
        c(
            "condition",
            "Original Chassis condition ( No Repair)",
            field="title",
            role="seller_condition",
        ),
        c("features", "New tires 2 keys"),
    ),
    record(
        "38",
        39,
        (
            "SF90 powertrain is stated asV8 plus eMotor; no petrol claim inferred. Assetto "
            "Fiorano is explicit package.0–100/top340kmh are performance, never odometer."
        ),
        c("features", "Assetto Fiorano Package", field="title", role="advertised_package"),
        c(
            "engine",
            "4.0L V8 Twin-Turbocharged Engine + eMotor",
            "V8 plus eMotor",
            role="configuration",
            conditions=(
                term("other", "4.0L V8 Twin-Turbocharged Engine + eMotor", "4.0", unit="litres"),
            ),
        ),
        c(
            "fuel_type",
            "Engine + eMotor",
            "combustion engine plus electric motor",
            disposition="ambiguous",
            reason="Powertrain pairing is explicit but fuel and hybrid subtype are not stated "
            "as such.",
        ),
        c(
            "transmission",
            "8 Speed Dual-Clutch Automatic Transmission",
            "dual-clutch automatic",
            conditions=(
                term("other", "8 Speed Dual-Clutch Automatic Transmission", 8, unit="gears"),
            ),
        ),
        c(
            "distance",
            "Top Speed 340 KM/H",
            340,
            unit="km_per_hour",
            role="performance_speed",
            disposition="excluded",
            reason="Speed, not odometer.",
        ),
        c(
            "features",
            "Carbon fibre Wheels - Yellow Brake Callipers - Wheel Stud Bolts in Titanium",
        ),
        c("features", "ADAS Full Pack - Surround View - Front and Rear Parking Sensors"),
    ),
    record(
        "39",
        40,
        (
            "Structured S versus title SQ4 unresolved trim. Full Service wording describes "
            "servicing, not necessarily complete historical records; insurance explicitly "
            "conditional on cash deal. Qualitative low mileage unavailable numerically."
        ),
        c("trim", "SQ4", "SQ4", field="title"),
        c("engine", "V6", "V6", field="title", role="configuration"),
        c("regional_specs", "GCC", "GCC", field="title"),
        c(
            "service_history",
            "Recently Serviced",
            "recently serviced; full historical record not established",
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
            reason="Insurance benefit is conditional on cash deal.",
            conditions=(
                term("scope", "1 Year Free Insurance (FOR CASH DEALS ONLY)", "cash deals only"),
            ),
        ),
        c("condition", "Guaranteed Accident Free", role="seller_condition"),
        c("condition", "Single Owner", role="ownership"),
        c(
            "mileage_km",
            "LOW MILEAGE",
            field="title",
            disposition="ambiguous",
            reason="No numeric odometer.",
        ),
    ),
    record(
        "40",
        41,
        (
            "2024 model differs from unnumbered new-facelift statement; no facelift year "
            "invented.5year Gargash warranty and3year service contract are source offers with "
            "start/current validity unspecified. Mild hybrid explicitly stated."
        ),
        c("body_type", "SUV", "SUV", field="title"),
        c("regional_specs", "GCC", "GCC", field="title"),
        c(
            "facelift_year",
            "New Facelift",
            field="title",
            disposition="ambiguous",
            reason="Facelift stated but no facelift year supplied.",
        ),
        c(
            "warranty",
            "5 Years Gargash Auto Warranty",
            "5 years Gargash Auto warranty; start/current validity not established",
            field="title",
            conditions=(
                term("duration", "5 Years Gargash Auto Warranty", 5, unit="years", field="title"),
                term("provider", "5 Years Gargash Auto Warranty", "Gargash Auto", field="title"),
            ),
        ),
        c(
            "service_plan",
            "3 Years Service Contract",
            "3 year service contract",
            occurrence=0,
            conditions=(
                term(
                    "duration",
                    (
                        '2024 Model, 21" Alloy Wheels, 5 Years Gargash Auto Warranty and 3 Years '
                        "Service Contract"
                    ),
                    3,
                    unit="years",
                ),
            ),
        ),
        c("fuel_type", "EQ Boost mild-hybrid technology", "mild hybrid"),
        c(
            "engine",
            "3.0L turbocharged inline-6 engine",
            "inline-6",
            role="configuration",
            conditions=(term("other", "3.0L turbocharged inline-6 engine", "3.0", unit="litres"),),
        ),
        c("transmission", "9G-TRONIC automatic transmission", "automatic"),
        c("features", "AMG body styling package", role="advertised_package"),
        c(
            "features",
            (
                "Panoramic sunroof LED Intelligent Light System MBUX infotainment system Dual "
                "12.3-inch digital displays"
            ),
        ),
        c("features", "7-seat configuration", "7 seats"),
        c("features", "Heated & ventilated front seats Power adjustable seats with memory"),
        c(
            "features",
            (
                "EASY-ENTRY third-row access Four-zone climate control Adaptive cruise control "
                "Lane keeping assist Blind spot monitoring 360-degree camera Parking assist "
                "Head-up display"
            ),
        ),
    ),
)
