# Revision 02 — clearer automotive headers and UAE app icon

24 September 2026. Canonical root: `${PROJECT_ROOT}`.

Use this **new mapping** for Frontend's next proof. Brain did not select the earlier stitching macro or blank facade. All older assets, manifests, reports and the complete official SVG remain unchanged as evidence; this revision replaces their mapping, not their bytes. Homepage/comparison art and factual listing photographs stay as they are.

| Surface | Asset | Dimensions / bytes | Proposed cover position |
| --- | --- | --- | --- |
| Browse | `../discovery-road.jpg` — retained | 1600 × 1067 / 379,865 | `50% 68%` |
| Detail | `detail-cabin.jpg` — new | 1600 × 1067 / 187,913 | `50% 65%` |
| Viewing preparation/review | `viewing-parked-car.jpg` — new | 1600 × 1013 / 239,253 | `50% 80%` |
| Outcome | `../outcome-horizon.jpg` — retained | 1600 × 2400 / 899,098 | `50% 24%` |

The new cabin visibly contains a steering wheel, gauges and dashboard; the new viewing image contains a complete warm-lit SUV on a road. Both are landscape sources and total **427,166 bytes**. All are solely decorative editorial images. The Subaru/WRX and Hyundai marks remain in the original photos; they do not identify the selected listing or establish its interior, features, equipment, condition, location or availability. Do not place these assets in the factual listing photo gallery. Use empty decorative alt text and live HTML headings/actions.

Starting layout remains desktop art on the right 44% of an approximately 160–200px header and a separate approximately 112px mobile strip. Keep the new photos' white fade mainly within the left 20% of their image region. For the parked car, keep the art ratio at or below about **4:1** so the roof and wheels fit; 4:1 leaves little margin. Cabin framing keeps the upper wheel/hub/dashboard, not the complete wheel circumference. Recheck any cabin ratio wider than about 3.5:1. Full images were inspected; these crop calculations are **not app-render proof**. Frontend owns actual laptop/mobile inspection before acceptance.

## Symbol before the name

`dubizzle-uae-app-icon.webp` is the actual icon from the [official UAE app listing](https://apps.apple.com/ph/app/dubizzle/id892172848), published by dubizzle. It is **400 × 400, 11,422 bytes**, with a red/black symbol on its original white rounded tile and **no embedded wordmark**. It can precede the existing dubizzle name without duplicate words. Start at 28–32px square; preserve the whole tile, source pixels and proportions. Give the overall brand/link one accessible name.

The original `../brand/dubizzle-official-lockup.svg` remains the complete-logo fallback. Use either the icon plus existing name **or** the complete lockup; do not combine both into a double brand treatment. This is a verified official app identity image, not a claimed brand-kit standalone vector. Source retrieval does not establish a third-party reuse license. Check actual small-size clarity and alignment in the header.

## Provenance and checks

- Cabin: [Agentseed on Unsplash](https://unsplash.com/photos/the-interior-of-a-car-with-a-steering-wheel-and-dashboard-0KJlYHZhPWs); exact metadata in `detail-cabin.json`.
- Parked car: [Hyundai Motor Group on Unsplash](https://unsplash.com/photos/a-car-parked-on-a-road-8kcsgLDAETg); exact metadata in `Records/build/studio/header-set/revision-02/viewing-source.json` from the project root.
- Both source pages displayed the free [Unsplash License](https://unsplash.com/license). Response bytes were preserved, with no local retouch, crop or re-encoding.
- `manifest.json` includes all selected paths, SHA-256 hashes, dimensions, source/credit links and constraints. Verification and reports are under `Records/build/studio/header-set/revision-02/`.
- The existing ChatGPT request was checked once during this correction. It was idle and exposed no new generated image artifact. No duplicate request or alternate generation was used.

Source checks passed. Frontend/Brain still own actual responsive render acceptance. No production source/public file, runtime or browser build was changed by Studio.
