# Testing Plan

## Dataset

The POC set has 25 synthetic English inquiries with manual labels:

| Category | Cases |
|---|---:|
| Gaming mouse | 5 |
| Mechanical keyboard | 6 |
| Gaming headset | 4 |
| Custom cable | 5 |
| Custom keycap | 5 |

It covers eight complete high-value cases, seven incomplete cases, five ODM cases, three low-quality cases, and two risk cases.

## Metrics

- Field extraction compares category, quantity, and country.
- Product match compares the recommended SKU.
- Priority accuracy compares High, Medium, Low, or Risk Review.
- Missing recall measures labeled missing fields found by the checker.
- Tool success measures completed workflow tools.
- Reply completeness checks minimum length, sign-off, and review notice.

## Baseline

The deterministic baseline is 97.3% field extraction, 100% product matching, 100% priority classification, 97.4% missing-field recall, 100% tool success, and 100% reply completeness on this set.

## Limitation

The same rules helped create and tune this bounded synthetic set, so these metrics measure regression readiness, not external validity. The next meaningful test is a blinded, anonymized sample of real inquiries reviewed by experienced salespeople.

