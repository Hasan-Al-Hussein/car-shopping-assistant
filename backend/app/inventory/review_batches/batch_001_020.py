"""Lead-reviewed records 1–20; independent semantic review pending."""

from app.inventory.review_authoring import cash, finance, mileage, record, term
from app.inventory.review_authoring import claim as c

RECORDS = (
    record(
        "1",
        2,
        (
            "Short title/description agree. 'calen' is not repaired into a verified condition. "
            "No price, mileage, warranty or history stated."
        ),
        c("regional_specs", "GCC", "GCC", field="title"),
        c("features", "silver color", "silver exterior", field="title", role="color"),
        c(
            "condition",
            "calen car",
            field="title",
            disposition="ambiguous",
            reason="Unclear spelling not repaired into factual condition.",
        ),
    ),
    record(
        "2",
        3,
        (
            "USA/engine title claims retained. Showroom address is dealer context, not proved "
            "vehicle location. AMG SPEC does not replace C300 Luxury trim."
        ),
        c("regional_specs", "USA", "USA", field="title"),
        c("engine", "2.0T", "2.0T", field="title", role="advertised_engine"),
        c(
            "features",
            "AMG SPEC",
            field="title",
            disposition="ambiguous",
            reason=(
                "Unspecified AMG specification claim does not establish a factory trim or "
                "exact equipment."
            ),
        ),
        c(
            "location",
            "Showroom No : 143, Ducamz, Ras Al Khor, Dubai, U.A.E",
            subject="dealer",
            disposition="dealer_wide",
            reason="Dealer showroom address, not a separate vehicle-location statement.",
        ),
    ),
    record(
        "3",
        4,
        (
            "Cash and two monthly offers are distinct; down-payment/term conditions retained. "
            "SUV and automatic are explicitly stated, not inferred from model. Warranty is a "
            "seller assertion without current validity proof."
        ),
        cash("AED 119,750.00 in cash", 11975000),
        finance("AED 2,111.00 monthly for 5 years with 10% Down-Payment", 211100, down=10, years=5),
        finance("AED 1,876.00 monthly for 5 years with 20% Down-Payment", 187600, down=20, years=5),
        mileage("Mileage: Just 68,000 km", 68000),
        c("trim", "Trim: R-Dynamic SE", "R-Dynamic SE"),
        c("body_type", "this SUV", "SUV"),
        c(
            "transmission",
            "Transmission: 8-speed automatic (AT)",
            "automatic",
            conditions=(term("other", "Transmission: 8-speed automatic (AT)", 8, unit="gears"),),
        ),
        c(
            "engine",
            "2.0 L I4 engine",
            "I4",
            role="configuration",
            conditions=(term("other", "2.0 L I4 engine", "2.0", unit="litres"),),
        ),
        c("regional_specs", "Regional Specs: GCC specifications", "GCC"),
        c(
            "warranty",
            "this vehicle comes with GCC warranty",
            "GCC warranty stated; provider, term and current validity not established",
        ),
        c("features", "Seating Capacity: 5 with plush beige interior", "5 seats; beige interior"),
        c("condition", "Impeccably maintained and in good condition", role="seller_condition"),
        c("features", "Drive Type: Automatic AWD", "AWD", role="drivetrain"),
        c("engine", "250 hp", 250, role="power", unit="hp"),
        c("features", "Rim size 16″", "16 inch rims"),
    ),
    record(
        "4",
        5,
        (
            "Unresolved E400/E450 trim claims. Japanese specification, odometer and seller "
            "condition/equipment are explicit; no independent inspection implied."
        ),
        c("trim", "E 450", "e 450", field="title"),
        mileage("Mileage - 56,000 KM", 56000),
        c("regional_specs", "JAPANESE SPECS", "Japanese", field="title"),
        c("body_type", "COUPE", "coupe", field="title"),
        c(
            "condition",
            "No Paint No Accident",
            "No paint/no accident claimed",
            role="seller_condition",
        ),
        c(
            "features",
            (
                "Lane assist Radar Adaptive Cruise Control Heads Up Display Auto park 360 ° "
                "Camera Sunroof AMG Rims Brumester Surround Sound System"
            ),
        ),
    ),
    record(
        "5",
        6,
        (
            "C63 AMG title agrees with structured trim. Numeric mileage and explicit V8/4.0 "
            "engine kept. No fuel type inferred from engine or badge."
        ),
        mileage("Mileage - 48000 KM", 48000),
        c("regional_specs", "JAPANESE SPECS", "Japanese", field="title"),
        c("body_type", "COUPE", "coupe", field="title"),
        c(
            "engine",
            "V8 4.0 biturbo",
            "V8",
            role="configuration",
            conditions=(
                term("other", "V8 4.0 biturbo", "4.0 biturbo; displacement unit unstated"),
            ),
        ),
        c(
            "features",
            (
                "Panoramic sunroof Red / black interior Lane assist Adaptive cruise control "
                "Radar Paddle shifter Ambient light Brumester surround sound system"
            ),
        ),
    ),
    record(
        "6",
        7,
        (
            "120000 km has explicit distance unit; bare30500 lacks currency and price role and "
            "is excluded from cash. Features are source claims."
        ),
        mileage("120,000 km", 120000, field="title"),
        c(
            "money",
            "30500",
            30500,
            field="title",
            role="unclassified_amount",
            unit="currency_unknown",
            disposition="ambiguous",
            reason="Bare figure has neither stated currency nor explicit price role; never "
            "AED cash.",
        ),
        c("regional_specs", "GCC", "GCC", field="title"),
        c("engine", "1.5L", "1.5", role="displacement", unit="litres"),
        c("features", "keyless open keyless start parking sensor Bluetooth panoramic roof"),
        c("condition", "in good condition", role="seller_condition"),
    ),
    record(
        "7",
        8,
        (
            "P900 title identifies this listing; long English/Arabic dealer inventory "
            "advertising supplies no vehicle price, location, body/fuel or availability facts."
        ),
        c("features", "P900 ROCKET ONE OF TEN", field="title", role="advertised_edition"),
        c(
            "location",
            (
                "Visit our showroom: Stoub Biz Motors, Showroom 50, Block 5, Al Aweer Auto "
                "Market (New), Ras Al Khor, Dubai."
            ),
            subject="dealer",
            disposition="dealer_wide",
            reason="Showroom invitation, not verified vehicle location.",
        ),
        c(
            "condition",
            "We can obtain new models that are sold out",
            subject="dealer",
            disposition="dealer_wide",
            reason="Dealer acquisition advertising does not establish this car's newness or "
            "availability.",
        ),
    ),
    record(
        "8",
        9,
        (
            "Seller says second owner and timely servicing; that is not converted to full "
            "documentary history. No numeric odometer/price provided."
        ),
        c("regional_specs", "GCC", "GCC", field="title"),
        c(
            "service_history",
            "all services done on time",
            "Seller states all services done on time; documentation not established",
        ),
        c("condition", "Am the second owner", "second owner claimed", role="ownership"),
        c("condition", "mechanically in great condition", role="seller_condition"),
        c(
            "features",
            "fully loaded with all the options",
            disposition="ambiguous",
            reason="No specific equipment is identified by fully-loaded language.",
        ),
    ),
    record(
        "9",
        10,
        (
            "Mansory/excellent-condition advertising retained without specific inferred "
            "equipment, cash, mileage or body classification."
        ),
        c("features", "FULL MANSORY", field="title", role="advertised_customization"),
        c("condition", "EXCELLENT CONDITION", field="title", role="seller_condition"),
    ),
    record(
        "10",
        11,
        (
            "Explicit42000 km and GCC; dealer's arrangeable warranty/service/finance are "
            "optional services, not included vehicle benefits."
        ),
        mileage("DONE 42,000KM", 42000, field="title"),
        c("regional_specs", "GCC", "GCC", field="title"),
        c(
            "warranty",
            "A warranty can be arranged",
            subject="dealer",
            disposition="conditional",
            reason="Arrangeable dealer service; no warranty inclusion/current coverage "
            "established.",
        ),
        c(
            "service_plan",
            "A service contract can be arranged",
            subject="dealer",
            disposition="conditional",
            reason="Optional service-plan arrangement, not service history or included contract.",
        ),
        c(
            "location",
            "Our showroom is located in the heart of Dubai’s automobile trading, Sheikh Zayed road",
            subject="dealer",
            disposition="dealer_wide",
            reason="Dealer address does not independently identify the vehicle location.",
        ),
    ),
    record(
        "11",
        12,
        (
            "RAK is explicitly labelled location. Accident-free is attributed to seller; no "
            "cash/mileage/warranty inferred."
        ),
        c("regional_specs", "GCC", "GCC", field="title"),
        c("location", "Location & RAK", "RAK"),
        c("condition", "Accident free", field="title", role="seller_condition"),
    ),
    record(
        "12",
        13,
        (
            "Cash35000 AED and salary3000 AED are separate. Finance document requests are "
            "inert dealer conditions. Numeric Mazda3 survives; no salary-as-price or inferred fuel."
        ),
        cash("PRICE REDUCED 35000 AED", 3500000),
        c(
            "money",
            "Salary Required:- AED 3000/-(WPS)",
            300000,
            role="salary",
            unit="minor_units",
            currency="AED",
            basis="salary",
            qualifier="at_least",
            conditions=(
                term("scope", "Salary Required:- AED 3000/-(WPS)", "WPS"),
                term("other", "Salary Certificate (AED 3000 and More)", "minimum3000AED"),
            ),
        ),
        c(
            "money",
            "Bank Auto finance can be arrange at 0% down payment",
            0,
            role="down_payment",
            unit="percent",
            disposition="conditional",
            reason="Arrangeable bank finance, not guaranteed eligibility.",
        ),
        c("regional_specs", "GCC Spec", "GCC", field="title"),
        c("engine", "1.6 ltr engine", "1.6", role="displacement", unit="litres"),
        c("condition", "100% Accident Free", role="seller_condition"),
        c(
            "condition",
            "Single Hand Used Car",
            "used car; single hand claimed",
            field="title",
            role="newness",
        ),
        c(
            "features",
            (
                "Cruise Control Bluetooth Systems ABS Brake Systems Parking Sensors Keyless "
                "Entry USB Pot Audio Aux In"
            ),
        ),
        c(
            "transmission",
            "Fully Automatic Power Mirror",
            disposition="ambiguous",
            reason=(
                "Automatic modifies power mirror/equipment in this list; not a reliable "
                "transmission statement."
            ),
        ),
    ),
    record(
        "13",
        14,
        (
            "Payment54500 AED is separate from insurance/evaluation/registration costs. "
            "Partial agency history and odometer explicit. V4 preserved as seller text without "
            "correcting to I4."
        ),
        cash("Payment:  AED 54,500", 5450000),
        c(
            "money",
            "AED 1,000 – Evaluation.",
            100000,
            role="fee",
            unit="minor_units",
            currency="AED",
            basis="fee",
        ),
        c(
            "money",
            "AED 1,200 – RTA/Car registration fee.",
            120000,
            role="fee",
            unit="minor_units",
            currency="AED",
            basis="fee",
        ),
        c(
            "money",
            "Approx. 2.5% for Car insurance.",
            "2.5",
            role="insurance_rate",
            unit="percent",
            qualifier="approximate",
            basis="fee",
        ),
        mileage("Odometer: 111,000 KM", 111000),
        c(
            "service_history",
            "Service History: Partial Agency Maintained",
            "partial agency service history",
        ),
        c(
            "transmission",
            "Transmission: 6 Speed Automatic",
            "automatic",
            conditions=(term("other", "Transmission: 6 Speed Automatic", 6, unit="gears"),),
        ),
        c(
            "engine",
            "Engine: V4 1.8TC",
            "V4",
            role="configuration",
            conditions=(term("other", "Engine: V4 1.8TC", "1.8TC"),),
        ),
        c("regional_specs", "Specs: GCC", "GCC"),
        c(
            "features",
            (
                "Xenon Headlights \uf0d8 Navigation \uf0d8 Rear camera \uf0d8 Electric "
                "sunroof \uf0d8 Alcantara "
                "Recaro seats \uf0d8 Parking sensors \uf0d8 Bose sound system \uf0d8 Blind spot "
                "indicators"
            ),
        ),
        c(
            "location",
            "Location: Ready2Ride Motors – Dubai Investment Park",
            "Dubai Investment Park; Ready2Ride Motors",
        ),
    ),
    record(
        "14",
        15,
        (
            "Only structured identity, GCC, seller condition and explicit equipment. Dealer "
            "showroom invitation is not vehicle location. No numeric mileage or price."
        ),
        c("regional_specs", "GCC", "GCC", field="title"),
        c("condition", "EXCELLENT CONDITION", field="title", role="seller_condition"),
        c(
            "features",
            (
                "Blind-spot monitoring Five surround cameras Self-parking system Panoramic "
                "roof Power-operated rear trunk Digital light projector"
            ),
        ),
        c(
            "features",
            "Heated front seats Navigation system Apple Carplay Android Auto Wireless "
            "phone charger",
        ),
        c(
            "features",
            "Dedicated areas for child seat installation",
            reason="Source describes installation areas, not a named restraint standard.",
        ),
        c("features", "19-inch black wheels", "19 inch black wheels"),
        c(
            "features",
            (
                "64-color interactive lighting Electrically-controlled seats with memory "
                "Digital gauge with customizable display"
            ),
        ),
    ),
    record(
        "15",
        16,
        (
            "Explicit cash and finance terms; odometer18845 km. W12 is preserved despite "
            "possible world-knowledge disagreement. Generic 'expect' customizations withheld. "
            "Warranty available is conditional."
        ),
        cash("1,349,999 AED", 134999900),
        finance(
            "25,683 AED per Month with 20% Down Payment over 5 Years", 2568300, down=20, years=5
        ),
        c(
            "money",
            "0% Down Payment option also available (subject to lender terms &conditions)",
            0,
            role="down_payment",
            unit="percent",
            basis="down_payment",
            disposition="conditional",
            reason="Alternative financing subject to lender terms; not unconditional cash "
            "discount.",
        ),
        mileage("Odometer: 18,845 (kms)", 18845),
        c("body_type", "a bespoke luxury SUV", "SUV"),
        c("engine", "Cylinders: W12", "W12", role="configuration"),
        c(
            "warranty",
            "WARRANTY AVAILABLE",
            disposition="conditional",
            reason="Availability of an offer does not establish included/current warranty.",
        ),
        c("condition", "IMMACULATE CAR", field="title", role="seller_condition"),
        c(
            "features",
            (
                "Expect unique aerodynamic body kits, upgraded wheels, personalized interiors "
                "with premium materials, and potential performance enhancements."
            ),
            disposition="ambiguous",
            reason="Generic expectations/potential enhancements are not definite installed "
            "features.",
        ),
        c(
            "features",
            (
                "360 Camera – Front and Rear Sensors – Navigation – Electric Seats – Memory "
                "Seats – Burmester Sound – Cruise Control – Speed Limiter – Android Auto – "
                "Apple CarPlay"
            ),
        ),
        c(
            "location",
            (
                "Storage Address: 1 4th St – Al Quoz – Al Quoz Industrial Area 3 – Dubai, "
                "United Arab Emirates."
            ),
            "Al Quoz Industrial Area 3, Dubai; stated storage address",
        ),
    ),
    record(
        "16",
        17,
        (
            "Generic Pajero wording does not establish a contradiction with more specific "
            "structured Pajero Sport. Red color/GCC retained; calen not repaired."
        ),
        c("regional_specs", "GCC", "GCC", field="title"),
        c("features", "red color", "red exterior", field="title", role="color"),
        c(
            "condition",
            "calen car",
            field="title",
            disposition="ambiguous",
            reason="Unclear spelling not repaired into factual condition.",
        ),
    ),
    record(
        "17",
        18,
        (
            "Unresolved W12 versus V8 engine configuration. Performance speeds/0–100 are not "
            "mileage. Transmission is explicitly dual-clutch; engine fuel not inferred. Dealer "
            "location omitted."
        ),
        c("engine", "W12", "W12", field="title", role="configuration"),
        c(
            "engine",
            "Engine - 4.0L V8 Twin Turbo",
            "V8",
            role="configuration",
            conditions=(term("other", "Engine - 4.0L V8 Twin Turbo", "4.0", unit="litres"),),
        ),
        c(
            "transmission",
            "Transmission - 8 Speed Dual Clutch Transmission",
            "dual-clutch",
            conditions=(
                term("other", "Transmission - 8 Speed Dual Clutch Transmission", 8, unit="gears"),
            ),
        ),
        c("regional_specs", "Spec - European", "European"),
        c("body_type", "Coupe Convertible", "convertible"),
        c(
            "distance",
            "Max Speed - 198 mph/ 318km/h",
            "198 mph / 318 km/h",
            role="performance_speed",
            disposition="excluded",
            reason="Speed is not odometer or a distance claim usable for mileage.",
        ),
        c(
            "features",
            "Head Up Display - Night Vision - Active Cruise Control - Lane Assist - Lane Departure",
        ),
    ),
    record(
        "18",
        19,
        (
            "New condition means marketing appearance, not brand-new status; source describes "
            "previous service. Full services history retained as source claim. Finance "
            "requests are dealer workflow, not product actions."
        ),
        c("regional_specs", "-GCC", "GCC"),
        c("service_history", "Full services history", "full service history"),
        c(
            "condition",
            "New condition",
            field="title",
            role="newness",
            disposition="ambiguous",
            reason="New-condition wording does not establish a new vehicle.",
        ),
        c("condition", "No Accident -No paint", role="seller_condition"),
        c("features", "New tyres", role="advertised_equipment"),
        c("condition", "No mechanical problems", role="seller_condition"),
        c(
            "service_history",
            "recently‏ ‏Serviced",
            "recently serviced claimed",
            role="recent_service",
        ),
        c(
            "money",
            "WE ARRANGE FREE FINANCE WITH 00 DOWN PAYMENT",
            0,
            role="down_payment",
            unit="percent",
            subject="dealer",
            disposition="conditional",
            reason="Dealer finance arrangement offer; eligibility unstated.",
        ),
    ),
    record(
        "19",
        20,
        (
            "Unresolved xDrive20i versus xDrive20d; diesel not inferred. Exact Arabic "
            "automatic-transmission statement retained.93,000 km is explicit odometer; funding "
            "prose remains inert."
        ),
        c("trim", "X1 xDrive 20d", "xdrive20d"),
        c(
            "trim",
            "x1 d",
            "x1 d",
            field="title",
            disposition="ambiguous",
            reason=(
                "Incomplete variant label supports uncertainty but cannot resolve the20i/20d "
                "disagreement."
            ),
        ),
        mileage("MILEAGE: 93,000 KM", 93000),
        c("regional_specs", "Specs: KOREA", "Korea"),
        c("engine", "ENGINE SIZE: 2.0 L + Turbo", "2.0", role="displacement", unit="litres"),
        c("engine", "CYLINDER: 4", 4, role="cylinder_count"),
        c(
            "transmission",
            "8 سرعات القير الأوتوماتيكي",
            "automatic",
            conditions=(term("other", "8 سرعات القير الأوتوماتيكي", 8, unit="gears"),),
        ),
        c("condition", "السيارة بدون حوادث", "no accidents claimed", role="seller_condition"),
        c("features", "Panoramic roof"),
        c("condition", "Original Paint", "original paint claimed", role="seller_condition"),
        c("engine", "HORSEPOWER: 178", 178, role="power", unit="hp"),
        c("engine", "CC: 1998", 1998, role="displacement", unit="cc"),
        c("features", "كاميرا خلفية", "rear camera"),
        c("features", "شاحن تلفون وايرلس", "wireless phone charger"),
        c("features", "نظام النقطة العمياء", "blind-spot system"),
        c("features", "نظام مراقبة ضغط الإطارات", "tyre pressure monitoring"),
        c("features", "آبل كار بلاي/آندرويد أوتو", "Apple CarPlay/Android Auto"),
        c(
            "features",
            "نظام القيادة الآلي",
            disposition="ambiguous",
            reason="Vague automatic-driving wording does not establish autonomy level/capability.",
        ),
        c(
            "features",
            "بصمة تشغيل",
            disposition="ambiguous",
            reason="Colloquial start feature wording not expanded into biometric capability.",
        ),
    ),
    record(
        "20",
        21,
        (
            "164000 kms, AED21500 and explicit American specs. Convertible/engine/Tiptronic "
            "are stated; no fuel inferred."
        ),
        cash("AED 21,500/-", 2150000),
        mileage("164,000 kms", 164000),
        c("regional_specs", "American Specifications", "American"),
        c("body_type", "Soft top convertible", "convertible"),
        c("transmission", "Tiptronic Gears", "Tiptronic"),
        c(
            "engine",
            "3.7L 6 Cylinders",
            6,
            role="cylinder_count",
            conditions=(term("other", "3.7L 6 Cylinders", "3.7", unit="litres"),),
        ),
        c("features", "Climate control", role="advertised_equipment"),
        c("features", "Rear Parking Sensors", role="advertised_equipment"),
        c("condition", "IN VERY EXCELLENT CONDITION", field="title", role="seller_condition"),
        c("engine", "300 BHP", 300, role="power", unit="bhp"),
        c("features", "Silver with Fabric interior", role="color"),
        c("features", "Cruise Control 4. Bluetooth System", "cruise control; Bluetooth"),
        c("features", "Fog Lights 10. Dual Exhaust", "fog lights; dual exhaust"),
    ),
)
