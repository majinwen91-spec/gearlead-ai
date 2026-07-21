# Database Design

SQLite stores three bounded domains:

- Catalog: `products` plus one category-specific spec table per product family
- Customer context: `customers`
- Workflow records: `crm_leads` and `lead_events`

```mermaid
erDiagram
    PRODUCTS ||--o| MOUSE_SPECS : has
    PRODUCTS ||--o| KEYBOARD_SPECS : has
    PRODUCTS ||--o| HEADSET_SPECS : has
    PRODUCTS ||--o| CABLE_SPECS : has
    PRODUCTS ||--o| KEYCAP_SPECS : has
    CRM_LEADS ||--o{ LEAD_EVENTS : records
```

The main product table holds shared commercial attributes such as MOQ, prices, lead time, certifications, markets, and customization flags. Category tables keep technical fields typed and queryable without forcing unrelated sparse columns into one table.

Seed data is stored in CSV and loaded idempotently. Runtime CRM data is written to `gearlead.db`, which is ignored by Git.

