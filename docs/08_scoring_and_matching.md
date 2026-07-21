# Scoring and Matching

## Matching

The matcher filters by category, evaluates category-specific fields, adds MOQ, certification, and market evidence, and returns the top three. Category-defining fields receive higher weight. Every candidate contains `reasons` and `gaps`.

Decision rules:

- Standard match: high technical score and no requested customization.
- Light customization: standard base plus supported logo, color, or packaging.
- ODM review: firmware, tooling, new mold, artwork, unsupported language, or structural work.
- No match: unknown category, no usable specifications, low fit without ODM support, or no active catalog product.

## Scoring

The score follows the PRD exactly: credibility 20, clarity 20, MOQ 15, feasibility 20, commercial value 15, urgency 10. High is 80+, Medium 60-79, and Low below 60. Explicit risk evidence overrides the total to `Risk Review`.

The score is an operational prioritization aid. It is not credit scoring, fraud detection, or an automatic rejection mechanism.

