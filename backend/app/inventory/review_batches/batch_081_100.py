"""Lead-reviewed records 81–100; independent semantic review pending."""

from app.inventory.review_authoring import cash, finance, mileage, record, term
from app.inventory.review_authoring import claim as c

RECORDS = (
    record(
        "81",
        82,
        (
            "Japan import/black interior/clean condition explicit; low mileage lacks a numeric "
            "reading. Dealer biography does not supply vehicle facts."
        ),
        c("regional_specs", "FRESH JAPAN IMPORT", "Japan import", field="title"),
        c("features", "Black Interior", "black interior", role="color"),
        c("condition", "Neat & Clean Car", role="seller_condition"),
        c("mileage_km", "Low Mileage", disposition="ambiguous", reason="No numeric odometer."),
    ),
    record(
        "82",
        83,
        (
            "Black Badge supplies trim while structuredOther is uninformative. Dealer warranty "
            "and dealer full service history are attached to this specific car, terms/current "
            "warranty validity unstated."
        ),
        c("trim", "BLACK BADGE", "Black Badge", field="title"),
        c("regional_specs", "GCC", "GCC", field="title"),
        c(
            "warranty",
            "DEALER WARRANTY",
            "dealer warranty stated; terms/current validity not established",
            field="title",
            conditions=(term("provider", "DEALER WARRANTY", "dealer unspecified", field="title"),),
        ),
        c("service_history", "DEALER FULL SERVICE HISTORY", "dealer full service history claimed"),
        c("condition", "EXCELLENT CONDITION", field="title", role="seller_condition"),
        c("features", "SPECIAL ORDERED", role="advertised_customization"),
    ),
    record(
        "83",
        84,
        (
            "S63s spelling differs from structuredS63AMG; do not invent alias or exact revised "
            "trim.4MaticPlus is explicit advertised descriptor. Low mileage not numeric."
        ),
        c(
            "trim",
            "S63s AMG",
            "S63s AMG",
            field="title",
            disposition="ambiguous",
            reason=(
                "Extra s may be variant/spelling; no approved equivalence to structuredS63AMG "
                "or correction."
            ),
        ),
        c("regional_specs", "FRESH JAPAN IMPORT", "Japan import", field="title"),
        c("features", "4Matic Plus", role="drivetrain"),
        c("features", "6 BUTTONS", field="title"),
        c("features", "Black Interior • Dynamic Seats • Cooling Seats"),
        c("condition", "Neat & Clean Car", role="seller_condition"),
        c("mileage_km", "Low Mileage", disposition="ambiguous", reason="No numeric odometer."),
    ),
    record(
        "84",
        85,
        (
            "Brand-new/LWB/limited edition/GCC explicit. Specific with-warranty-and-service "
            "offer distinguished from arrangeable dealer boilerplate. Service meaning "
            "unspecified, not historical servicing."
        ),
        c("condition", "Brand NEW", "brand new claimed", field="title", role="newness"),
        c("regional_specs", "GCC", "GCC", field="title"),
        c("features", "LWB LIMITED EDITION ( 1 OF 1)", field="title", role="advertised_edition"),
        c(
            "warranty",
            "With Warranty + Service",
            "warranty offered; provider/terms/current validity unspecified",
            field="title",
        ),
        c(
            "service_plan",
            "With Warranty + Service",
            field="title",
            disposition="ambiguous",
            reason=(
                "Service benefit mentioned without identifying included plan, duration or "
                "scope; not service history."
            ),
        ),
        c(
            "warranty",
            "A warranty can be arranged",
            subject="dealer",
            disposition="conditional",
            reason="Dealer-wide optional arrangement distinct from vehicle-specific title "
            "warranty.",
        ),
    ),
    record(
        "85",
        86,
        (
            "Brabus edition andBurmester source title claims. Low mileage qualitative; "
            "reference12539 not odometer/price. Warranty/service availability belongs to "
            "dealer privilege list, not car inclusion."
        ),
        c("features", "BRABUS ROCKET 900 1 OF 10", field="title", role="advertised_customization"),
        c("features", "BURMESTER SOUND", field="title"),
        c(
            "mileage_km",
            "LOW MILEAGE",
            field="title",
            disposition="ambiguous",
            reason="No numeric odometer.",
        ),
        c(
            "warranty",
            "Warranty & Service Contract available",
            subject="dealer",
            disposition="conditional",
            reason="Dealer privileges availability without listing-specific inclusion or terms.",
        ),
        c(
            "service_plan",
            "Warranty & Service Contract available",
            subject="dealer",
            disposition="conditional",
            reason="Dealer privileges availability without included vehicle service plan.",
        ),
    ),
    record(
        "86",
        87,
        (
            "Brand-new and3free services are vehicle-specific. Generic performance paragraph "
            "retained without odometer or fuel-type inference. Arrangeable warranty remains "
            "dealer scope."
        ),
        c("condition", "BRAND NEW", "brand new claimed", field="title", role="newness"),
        c(
            "service_plan",
            "CAR HAS 3 FREE SERVICES",
            "3 free services stated; scheduling/terms unspecified",
            role="included_benefit",
        ),
        c(
            "engine",
            "V12 and electric drive units",
            "V12 plus electric drive units",
            subject="unspecified",
            disposition="ambiguous",
            reason=(
                "Generic model-performance paragraph, not separately verified configuration of "
                "individual vehicle."
            ),
        ),
        c(
            "distance",
            "Top speed is 217 mph",
            217,
            unit="mph",
            role="performance_speed",
            disposition="excluded",
            reason="Speed is not odometer.",
        ),
        c(
            "warranty",
            "A warranty can be arranged",
            subject="dealer",
            disposition="conditional",
            reason="Optional dealer service, not included vehicle warranty.",
        ),
    ),
    record(
        "87",
        88,
        (
            "Chassis identifier not mileage or price. Panoramic roof/leather/reverse "
            "camera/original airbags and chassis condition are seller claims."
        ),
        c(
            "features",
            "leather Seats Panoramic roof Screen with revere camera",
            "leather seats; panoramic roof; reverse camera claimed",
        ),
        c(
            "condition",
            "Excellent condition Original air bags original Chassis condition ( No repair)",
            role="seller_condition",
        ),
    ),
    record(
        "88",
        89,
        (
            "115000AED cash distinct from2300/1850monthly plans;15858km. Hyundai/Genesis "
            "labels preserved without brand migration;G80 retained as advertised model "
            "descriptor. Third-party2year warranty is source claim, not current verification."
        ),
        cash("AED 115,000 cash", 11500000),
        finance(
            "AED 2,300 monthly for 5 years with 0% Down-Payment / flexible",
            230000,
            down=0,
            years=5,
            flexible=True,
        ),
        finance(
            "AED 1,850 monthly for 5 years with 20% Down-Payment / flexible",
            185000,
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
            reason="Shared financing offer wording; exact eligibility/scope unspecified.",
        ),
        mileage("Odometer : 15,858 Kms", 15858),
        c(
            "warranty",
            "Warranty : 3rd Party (2 Years)",
            "third-party2year warranty; start/current validity unverified",
            conditions=(
                term("duration", "Warranty : 3rd Party (2 Years)", 2, unit="years"),
                term("provider", "Warranty : 3rd Party (2 Years)", "third party"),
            ),
        ),
        c("regional_specs", "Specification : Korean", "Korean"),
        c(
            "engine",
            "Cylinders : V6 3.0L",
            "V6",
            role="configuration",
            conditions=(term("other", "Cylinders : V6 3.0L", "3.0", unit="litres"),),
        ),
        c(
            "features",
            "Hyundai Genesis G80",
            "G80 advertised descriptor",
            role="advertised_variant",
        ),
        c(
            "features",
            "Free Insurance + Registration",
            field="title",
            disposition="conditional",
            reason="Offer inclusion/terms unspecified.",
        ),
    ),
    record(
        "89",
        90,
        (
            "Convertible explicit. GCC only dealer-wide statement, so not accepted per-car "
            "regional spec. Recent/full service performed is not complete history. Cash-only "
            "insurance conditional."
        ),
        c("body_type", "CONVERTIBLE", "convertible", field="title"),
        c(
            "regional_specs",
            "ALHOOT MOTORS DEALS WITH GCC CARS ONLY!",
            "GCC",
            subject="dealer",
            disposition="dealer_wide",
            reason="Dealer-wide stock claim without separate vehicle-specific specification.",
        ),
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
            reason="Cash-deal condition retained.",
            conditions=(
                term("scope", "1 Year Free Insurance (FOR CASH DEALS ONLY)", "cash deals only"),
            ),
        ),
        c("condition", "Guaranteed Accident Free", role="seller_condition"),
        c("condition", "Single Owner", role="ownership"),
    ),
    record(
        "90",
        91,
        (
            "GCC/white color explicit. Calen/fullopshin spellings not expanded into exact "
            "condition/equipment."
        ),
        c("regional_specs", "GCC", "GCC", field="title"),
        c("features", "white color", "white exterior", field="title", role="color"),
        c(
            "condition",
            "Calen car",
            disposition="ambiguous",
            reason="Unclear spelling not repaired into factual condition.",
        ),
    ),
    record(
        "91",
        92,
        (
            "Model2009 and facelift2025 refer to different concepts and are not conflicts. "
            "V6/4.0L/GCC and explicit installed equipment retained; no model-year overwrite."
        ),
        c("year", "model 2009", 2009, role="model_year"),
        c("facelift_year", "facelifted 2025", 2025, role="facelift_year"),
        c("regional_specs", "GCC", "GCC", field="title"),
        c(
            "engine",
            "engine v6 4.0L",
            "V6",
            role="configuration",
            conditions=(term("other", "engine v6 4.0L", "4.0", unit="litres"),),
        ),
        c("condition", "IN EXCELLENT CONDITION", field="title", role="seller_condition"),
        c(
            "features",
            (
                "front TV and 360° camera Leather seats Electric seat Headrests DVD'S New "
                "rim's and tyre's New steering control Push Start Cool box"
            ),
        ),
    ),
    record(
        "92",
        93,
        (
            "From5805AEDmonthly is lower-bound financing, not cash.23900km odometer distinct "
            "from optional up-to3year warranty/service offers. Unlimited claim limit does not "
            "mean unlimited mileage."
        ),
        finance("From AED 5,805/mo", 580500, field="title", qualifier="at_least"),
        mileage("Mileage: 23 900 kms", 23900),
        c("regional_specs", "Regional Specification: Japanese (4.5B Grade)", "Japanese"),
        c(
            "condition",
            "(4.5B Grade)",
            "grade4.5B claimed; grading scheme unstated",
            role="seller_grade",
        ),
        c(
            "warranty",
            (
                "Warranty Includes: • Unlimited claim limit • 24/7 Roadside Assistance • "
                "Extended Coverage • Can be extended up to 3 years"
            ),
            disposition="conditional",
            reason=(
                "Title presents warranty options; description permits extension up to3years, "
                "not unconditional3year coverage."
            ),
            conditions=(
                term("duration", "Can be extended up to 3 years", "up to3", unit="years"),
                term("other", "Unlimited claim limit", "unlimited claim limit; not mileage"),
            ),
        ),
        c(
            "service_plan",
            "Up to 3 years Service Contract available, including brake replacement package.",
            disposition="conditional",
            qualifier="at_most",
            reason=(
                "Optional available service contract with up-to duration, not included/current "
                "coverage."
            ),
        ),
        c("features", "Exterior: Diamond White Interior: Black", role="color"),
    ),
    record(
        "93",
        94,
        (
            "271000km explicit. AbuDhabi RahayelCity is attached directly to vehicle advert; "
            "no location inferred from dealer biography."
        ),
        mileage("271000km", 271000),
        c("location", "Abu Dhabi, Rahayel City", "Abu Dhabi, Rahayel City"),
    ),
    record(
        "94",
        95,
        (
            "GCC/gold color explicit. Calen andfullopshin not automatically repaired; other "
            "facts unavailable."
        ),
        c("regional_specs", "GCC", "GCC", field="title"),
        c("features", "gold color", "gold exterior", role="color"),
        c(
            "condition",
            "Calen car",
            disposition="ambiguous",
            reason="Unclear spelling not repaired into factual condition.",
        ),
    ),
    record(
        "95",
        96,
        (
            "RAV4 structured versus Wildlander narrative remains unresolved without invented "
            "alias.970km and95000AED cash explicit. Almost-new marketing does not mean new. "
            "Financing separate and conditions retained."
        ),
        c("model", "Toyota Wildlander AWD", "Wildlander"),
        cash("AED 95,000 cash", 9500000),
        finance(
            "AED 1,950 monthly for 5 years with 0% Down-Payment / flexible",
            195000,
            down=0,
            years=5,
            flexible=True,
        ),
        finance(
            "AED 1,500 monthly for 5 years with 20% Down-Payment / flexible",
            150000,
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
            reason="Financing offer wording; exact eligibility/scope unspecified.",
        ),
        mileage("Odometer : 970 Kms", 970),
        c(
            "warranty",
            "Warranty : 3rd Party (2 Years)",
            "third-party2year warranty; start/current validity unverified",
            conditions=(
                term("duration", "Warranty : 3rd Party (2 Years)", 2, unit="years"),
                term("provider", "Warranty : 3rd Party (2 Years)", "third party"),
            ),
        ),
        c("regional_specs", "Specification : Korea", "Korea"),
        c(
            "engine",
            "Cylinders : V4 2.5L",
            "V4",
            role="configuration",
            conditions=(term("other", "Cylinders : V4 2.5L", "2.5", unit="litres"),),
        ),
        c(
            "condition",
            "Almost New",
            field="title",
            role="newness",
            disposition="ambiguous",
            reason="Almost new is condition marketing, not brand-new status.",
        ),
        c(
            "features",
            "Free Insurance + Registration",
            field="title",
            disposition="conditional",
            reason="Offer eligibility/terms unspecified.",
        ),
        c("features", "AWD", "AWD", field="title", role="drivetrain"),
    ),
    record(
        "96",
        97,
        (
            "StructuredT5Momentum conflicts with B5FWD Momentum narrative; preserve both "
            "without fuel inference.71000km/GCC/engine/colours explicit."
        ),
        c("trim", "B5 FWD MOMENTUM", "B5 FWD Momentum", field="title"),
        mileage("Mileage: 71000 km", 71000),
        c("regional_specs", "GCC Specifications", "GCC"),
        c(
            "engine",
            "Engine: 2.0L Turbo 4 Cylinders",
            4,
            role="cylinder_count",
            conditions=(term("other", "Engine: 2.0L Turbo 4 Cylinders", "2.0", unit="litres"),),
        ),
        c("features", "Grey exterior with Beige leather interior", role="color"),
    ),
    record(
        "97",
        98,
        (
            "299000AED cash/65699km explicit. Convertible/V12/8automatic source-bound;6.0 "
            "lacks unit and not silently litres. AstonMartin service history does not "
            "establish complete record."
        ),
        cash("AED 299,000 /-", 29900000),
        mileage("Mileage 65,699 Kms", 65699),
        c("body_type", "Convertible", "convertible", field="title"),
        c("regional_specs", "GCC Specifications", "GCC"),
        c(
            "engine",
            "6.0 V12 RWD",
            "V12",
            role="configuration",
            conditions=(term("other", "6.0 V12 RWD", "6.0; unit unstated"),),
        ),
        c(
            "transmission",
            "8 Auto Speed Gearbox",
            "automatic",
            conditions=(term("other", "8 Auto Speed Gearbox", 8, unit="gears"),),
        ),
        c(
            "service_history",
            "Aston Martin Service History",
            "Aston Martin service history stated; completeness unspecified",
        ),
        c("condition", "Excellent Condition", role="seller_condition"),
        c(
            "features",
            (
                "Keyless Entry - Electric Leather Memory Seats - Heated Seats - Paddle Shifter "
                "- Cruise Control - Parking Sensors - Rear Camera"
            ),
        ),
        c(
            "features",
            "Bang & Olufsen Surround Sound System - Sports Suspension - Aston Martin Drive Modes",
        ),
    ),
    record(
        "98",
        99,
        (
            "Original Mileage does not give numeric reading. Location is expressly dealer "
            "location in showroom contact context, not asserted current car location.40years "
            "is dealership experience."
        ),
        c("mileage_km", "Original Mileage", disposition="ambiguous", reason="No numeric odometer."),
        c("condition", "Excellent condition", role="seller_condition"),
        c(
            "location",
            "Al Nabeel Used Cars Location: Souq Alharaj, Sharjah Showroom 304 Phase # 2",
            subject="dealer",
            disposition="dealer_wide",
            reason="Explicit dealer/showroom location, not vehicle-location assertion.",
        ),
    ),
    record(
        "99",
        100,
        (
            "GCC title vehicle-specific. Qualitative low mileage unavailable numerically; full "
            "service performed not complete history. Panoramic shorthand held without "
            "inventing an equipment type."
        ),
        c("regional_specs", "GCC", "GCC", field="title"),
        c(
            "mileage_km",
            "LOW MILEAGE",
            field="title",
            disposition="ambiguous",
            reason="No numeric odometer.",
        ),
        c(
            "features",
            "PANORAMIC",
            field="title",
            disposition="ambiguous",
            reason="Single adjective does not explicitly name equipment.",
        ),
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
            reason="Cash-deal condition retained.",
            conditions=(
                term("scope", "1 Year Free Insurance (FOR CASH DEALS ONLY)", "cash deals only"),
            ),
        ),
        c("condition", "Guaranteed Accident Free", role="seller_condition"),
        c("condition", "Single Owner", role="ownership"),
    ),
    record(
        "100",
        101,
        (
            "GTC Speed is a more specific advertised descriptor than structuredGTC, not "
            "automatically a contradiction. GCC explicit; warranty availability optional. "
            "Dealer400stock not mileage."
        ),
        c("features", "GTC SPEED", field="title", role="advertised_variant"),
        c("regional_specs", "GCC", "GCC", field="title"),
        c(
            "warranty",
            "WARRANTY AVAILABLE",
            field="title",
            disposition="conditional",
            reason="Warranty availability, not included/current coverage.",
        ),
    ),
)
