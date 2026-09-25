"""Reviewed declarations for one exact source; no automatic approval of new data."""

from app.inventory.review_batches.batch_001_020 import RECORDS as BATCH_1
from app.inventory.review_batches.batch_021_040 import RECORDS as BATCH_2
from app.inventory.review_batches.batch_041_060 import RECORDS as BATCH_3
from app.inventory.review_batches.batch_061_080 import RECORDS as BATCH_4
from app.inventory.review_batches.batch_081_100 import RECORDS as BATCH_5
from app.inventory.review_catalogue import FAMILIES, Family, FamilyOmission, ReviewCatalogue

# These are deliberately unpromoted additional source candidates, not source absence.
# Selected accepted claims in the same family remain available with partial coverage.
OMISSIONS: dict[str, tuple[Family, ...]] = {
    "4": ("condition",),
    "5": ("condition",),
    "12": ("features", "condition"),
    "13": ("engine",),
    "14": ("features",),
    "15": ("features",),
    "17": ("features", "engine"),
    "19": ("features",),
    "20": ("features",),
    "21": ("features", "condition"),
    "22": ("features",),
    "23": ("features", "money"),
    "24": ("condition",),
    "26": ("features", "money"),
    "34": ("features", "condition"),
    "37": ("condition",),
    "38": ("features", "engine"),
    "39": ("features", "condition", "service_history"),
    "40": ("features",),
    "44": ("engine", "features"),
    "49": ("features", "engine"),
    "54": ("engine",),
    "57": ("features",),
    "60": ("condition",),
    "63": ("features", "condition", "service_history"),
    "64": ("features", "condition"),
    "68": ("features", "money"),
    "75": ("features", "engine"),
    "77": ("features",),
    "79": ("service_history",),
    "86": ("engine",),
    "89": ("features", "condition", "service_history"),
    "97": ("features", "engine"),
    "99": ("features", "condition", "service_history"),
}


def provided_source_catalogue() -> ReviewCatalogue:
    records = []
    for review in (*BATCH_1, *BATCH_2, *BATCH_3, *BATCH_4, *BATCH_5):
        omissions = tuple(
            FamilyOmission(
                family=family,
                source_fields=("title", "description"),
                reason=(
                    "Additional source candidates were inspected but deliberately not "
                    "promoted by this bounded review. Original complete text is preserved; "
                    "this family is not exhaustively extracted or source-absent."
                ),
            )
            for family in OMISSIONS.get(review.source_id, ())
        )
        records.append(review.model_copy(update={"omissions": omissions}))
    return ReviewCatalogue(
        schema_version="review-catalogue-1",
        extraction_version="reviewed-claims-2",
        policy_version="DEMO-POLICY-1",
        namespace="provided-cars-cleaned",
        workbook_sha256="94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
        sheet="cleaned dataset",
        families=FAMILIES,
        review_state="approved",
        review_method=(
            "Lead full-context and independent all100-record/all-accepted-claim semantic "
            "inspection completed; corrections and masks closed;972 exact source bindings "
            "checked. This is source-review approval, not runtime acceptance, independent "
            "vehicle verification or publication."
        ),
        records=tuple(records),
    )
