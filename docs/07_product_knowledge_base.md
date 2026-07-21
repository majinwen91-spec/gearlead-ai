# Product Knowledge Base

The catalog contains 20 SKUs, four per category.

## Category-defining Fields

| Category | Primary fields |
|---|---|
| Gaming mouse | Connection, sensor, DPI, polling rate, weight, switch, shape |
| Mechanical keyboard | Layout, connection, mount, hot swap, material, profile, firmware, language |
| Gaming headset | Connection, driver, channel, microphone, battery, platforms |
| Custom cable | Form, connector pair, aviator, length, coil, sleeve, data standard |
| Custom keycap | Material, process, profile, layout, language, key count, artwork |

The structured SQL catalog is preferred over RAG because the core knowledge is tabular and comparisons require exact fields. A future RAG layer would be useful for manuals, certification reports, packaging guides, and product PDFs, but it should cite those documents rather than replace catalog filtering.

