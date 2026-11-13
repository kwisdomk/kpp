# Collecting KPP equipment images

Collection guidance, 13 November 2026. This does not approve new assets, change
the catalogue/label contract, or satisfy the image minimum by itself.

## Reach 30 images with useful coverage

The project minimum is 30 labeled images, alongside 15 documented products.
A workable collection target is two distinct captures per product: an equipment
overview and a readable model/nameplate image. That allocation is a team proposal,
not an official per-product minimum. Collect extra independent captures if
possible for lighting/angle variation and held-out testing.

1. Confirm the exact catalogue model first. A visually similar generator,
   inverter or pump is not evidence of that specific model.
2. Prioritize team-taken photos of safely accessible, powered-down equipment
   with the owner's permission, or photos contributed with recorded reuse rights.
   Do not open electrical equipment, remove guards or energize it for a photo.
3. Search Wikimedia Commons by exact manufacturer/model. Read each file's own
   source, author and license; record attribution and modifications. A broad
   equipment photo can illustrate a category but cannot acquire a specific model
   label just because it resembles one.
4. Use manufacturer/manual/press images only when their applicable terms or
   permission cover the intended processing, excerpts and publication. A public
   download or a search result is not an approved reuse record. Cropping an image
   out of a PDF does not remove its source rights requirements.
5. Record missing coverage honestly. If the current 15 candidates cannot be
   photographed or sourced legally, flag the affected slots to A/B before
   proposing substitutions; never silently change the catalogue or labels.

Wikimedia's own guidance requires checking each file and following its specific
attribution/license conditions:
https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia

## Labels and equipment relationships

Use the label fields already specified by `project-plan.md` section 6.1:
`image_id`, `product_id`, kind, `gold_model_id`, source/license, file hash,
label method, reviewer and split. Retain original capture/source grouping and
parent-image references in the reviewed label design before creating derivatives.
The human `JC-*` catalogue IDs and backend integer IDs still need an explicit
reviewed mapping; this guide does not choose a new schema.

An image depicts a product/component; its source record documents provenance;
the authorized product/source relationship controls retrieval. An overview image
may support category recognition; a readable model label supports OCR matching.
Neither proves diagnosis, installation suitability or compatibility. Those
relationships still require reviewed technical source evidence.

## Honest evaluation

- Decide development/held-out assignment before OCR tuning. Group the same
  equipment instance/capture session and all derivatives together; freeze IDs.
- A crop, rotated copy, brightness change or screenshot of the same original
  is not a new independent held-out capture. Hash originals and review near
  duplicates as well as exact duplicates.
- Keep readable nameplates for model identification. Report overview, nameplate,
  diagram and part results separately; do not imply OCR recognizes every part.
- Generated labels/nameplates are useful synthetic regression fixtures only.
  Do not treat them as photographed equipment or field-accuracy evidence.
- Have a second person verify exact model labels, provenance and split integrity.
  Record failures and unknown/unreadable models; do not guess their identity.

Practical team split: one person coordinates each of the three categories;
the fourth checks labels, rights and duplicate/split problems across categories.
These are proposed collection duties, not assigned names or new coding agents.
