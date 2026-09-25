# S19 cinematic header assets

Source-ready handoff, 24 September 2026. Canonical project: `${PROJECT_ROOT}`.

Frontend owns production integration. These four JPEG files are real sourced editorial photographs used as decoration. They do not depict or substantiate the selected listing, its features, a viewing venue or a booking outcome. Keep the approved homepage/comparison images and all original workbook listing images unchanged.

| Route | File | Intrinsic dimensions | Bytes | Proposed object-position |
| --- | --- | --- | --- | --- |
| Browse | `discovery-road.jpg` | 1600 × 1067 | 379,865 | `50% 68%` |
| Listing detail | `detail-material.jpg` | 1600 × 2404 | 530,890 | `50% 42%` |
| Viewing preparation/review | `viewing-arrival.jpg` | 1600 × 2400 | 659,959 | `50% 40%` |
| Outcome | `outcome-horizon.jpg` | 1600 × 2400 | 899,098 | `50% 24%` |

Use `object-fit: cover`; the native files deliberately retain their source aspect ratio. Desktop guidance is an image on the right 44% of a roughly 160–200px shallow header, fading toward the white title area. Mobile guidance is a separate approximately 112px-high strip above the title. The positions are proposed starting points, not claims of rendered app acceptance. Inspect browse on laptop/mobile before extending to other routes, then inspect each distinct crop. Keep the outcome's upper horizon crop: the full portrait source includes a small runner on the lower road. Use the facade as warm architecture, without labeling it a showroom or real destination.

The set totals 2,469,812 bytes. Load the current route's image, not all four. The larger files are full-aspect source assets; optimized production derivatives may be created and recorded by Frontend if needed. No local pixels were edited in this handoff. Use empty alternative text for purely decorative images and keep page text/actions as live HTML. A visible technical “editorial image” badge is not requested; the distinction belongs in this internal manifest and the separation from actual listing photos.

## Authentic branding

`brand/dubizzle-official-lockup.svg` is the complete official 111 × 36 lockup, 4,575 bytes. Use it **in place of** the existing wordmark. Do not append another dubizzle name or fabricate/extract a standalone symbol. The bounded search did not verify a separate complete symbol. Preserve source proportions/colors; source spelling quirks are documented in `brand/asset.json`. Browser scaling still needs Frontend proof. Official sourcing is established; third-party reuse permission is not established by the download.

## Source credits

- Discovery: [Grianghraf on Unsplash](https://unsplash.com/photos/winding-mountain-road-bathed-in-golden-hour-light-zHRtKTttbKg).
- Detail: [Lu on Unsplash](https://unsplash.com/photos/close-up-of-a-luxury-cars-leather-stitched-steering-wheel-4k3gjWxkCvU).
- Viewing: [Jason Sung on Unsplash](https://unsplash.com/photos/modern-glass-building-reflecting-the-sky-at-sunset-AZ1ObEayTUk).
- Outcome: [Venti Views on Unsplash](https://unsplash.com/photos/winding-road-in-the-mountains-during-sunset-nDIVpMiDfiw).
- Each source page displayed “Free to use under the [Unsplash License](https://unsplash.com/license)” at retrieval. Retain source/photographer records; this is not an Unsplash+ collection.
- Brand: [dubizzle official asset](https://static.dubizzle.com/static_assets/dubizzleLogo.svg), linked from its official homepage. See `brand/README.md` for exact-source constraints.

`manifest.json` supplies full paths, SHA-256 hashes, dimensions, source/download URLs, crop guidance and pending acceptance. The requested ChatGPT generation route was attempted; no new usable generated artifact was exposed at the final bounded check. This delivery therefore uses the authorized real-photo fallback. No generated-image success is claimed.
