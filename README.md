# IDF Reader — EnergyPlus Zone Metadata Extractor

A lightweight, dependency-minimal Python toolkit for parsing EnergyPlus `.idf` files, extracting zone-level building metadata, and generating structured reports with an embedded 3D geometry visualization.

---

## 📋 Overview

This project targets the **16 ASHRAE 90.1-2022 prototype buildings** (Denver climate zone) and produces:

- **HTML** — polished, dark-themed interactive report with an embedded 3D floor plan. Contains detailed zone metadata and HVAC system tables.

All values are normalized to standard SI units (W/m², m³/s·m², etc.) for direct comparison across building types.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🏗️ **3D Visualization** | Renders exterior + interior surfaces using Matplotlib. Windows, roofs, and floors are drawn in distinct styles. |
| 📊 **Zone Metadata Extraction** | Occupancy, lighting, electric/gas equipment, SHW, infiltration, ventilation, and thermostat setpoints — all normalized to floor or facade area. |
| 🗜️ **Smart Deduplication** | Identical thermal zones (e.g. 12 classrooms with the same loads) are collapsed into a single row with a `Count` column. |
| 🔢 **Clean Formatting** | Values are rounded to 4 significant decimals with trailing zeros stripped (`988` not `988.0000`, `15.6` not `15.6000`). |
| 🔄 **Multi-file Batch Mode** | Process all IDF files in the default directory in one command. |

---

## 📂 Project Structure

```
idf_reader/
│
├── main.py                    # Entry point: interactive menu & batch CLI
├── idf_parser.py              # Lightweight IDF tokeniser (no eppy required)
├── geometry.py                # Zone floor/facade area from BuildingSurface:Detailed
├── extractors.py              # One function per IDF object type → normalised dicts
├── report_generator.py        # CSV, Markdown & HTML report generation
├── visualizer_adapter.py      # 3D rendering with Matplotlib, returns base64 PNG
│
├── Content/                   # Data directory
│   └── ASHRAE901_STD2022/     # 16 EnergyPlus prototype IDF files (Denver, 2022)
├── docs/                      # Implementation plan and design notes
├── examples/                  # Standalone visualizer scripts
└── outputs/                   # Auto-generated reports (gitignored)
```

---

## 🚀 Quick Start

### 1. Install dependencies

```bash
pip install matplotlib numpy
```

> No `eppy` or EnergyPlus installation is required. The parser is fully self-contained.

### 2. Interactive mode (pick a file from a menu)

```bash
python main.py
```

### 3. Single-file mode

```bash
python main.py --idf Content/ASHRAE901_STD2022/ASHRAE901_OfficeLarge_STD2022_Denver.idf
```

### 4. Batch mode (process all IDF files)

```bash
python main.py --all
```

Reports are saved to the `outputs/` directory (created automatically) as `.html` files.

---

## 📊 Output Columns

| Column | Unit | Notes |
|---|---|---|
| Zone | — | Base name after deduplication suffix stripping |
| Count | — | Number of identical zones collapsed |
| Floor Area | m² | First zone's area (may vary across collapsed zones) |
| Occupancy | people/m² | Handles `People`, `People/Area`, `Area/Person` methods |
| Lighting | W/m² | Handles `LightingLevel`, `Watts/Area`, `Watts/Person` |
| Electric Equipment | W/m² | Handles same 3 methods |
| Gas Equipment | W/m² | Handles same 3 methods |
| SHW | L/(h·m²) | Converted from peak flow rate (m³/s) |
| Infiltration | m³/(s·m²_facade) | Normalized to exterior wall area |
| Ventilation | m³/(s·person) | Per-person ventilation rate |
| Ventilation | m³/(s·m²) | Per-area ventilation rate |
| Htg Setpoint | °C | Resolved from `Schedule:Compact` / `Schedule:Constant` |
| Clg Setpoint | °C | Resolved from `Schedule:Compact` / `Schedule:Constant` |

---

## 🏢 Included Buildings (ASHRAE 90.1-2022 · Denver, CO)

| Building Type | IDF File |
|---|---|
| Apartment — High Rise | `ASHRAE901_ApartmentHighRise_STD2022_Denver.idf` |
| Apartment — Mid Rise | `ASHRAE901_ApartmentMidRise_STD2022_Denver.idf` |
| Hospital | `ASHRAE901_Hospital_STD2022_Denver.idf` |
| Hotel — Large | `ASHRAE901_HotelLarge_STD2022_Denver.idf` |
| Hotel — Small | `ASHRAE901_HotelSmall_STD2022_Denver.idf` |
| Office — Large | `ASHRAE901_OfficeLarge_STD2022_Denver.idf` |
| Office — Medium | `ASHRAE901_OfficeMedium_STD2022_Denver.idf` |
| Office — Small | `ASHRAE901_OfficeSmall_STD2022_Denver.idf` |
| OutPatient Health Care | `ASHRAE901_OutPatientHealthCare_STD2022_Denver.idf` |
| Restaurant — Fast Food | `ASHRAE901_RestaurantFastFood_STD2022_Denver.idf` |
| Restaurant — Sit Down | `ASHRAE901_RestaurantSitDown_STD2022_Denver.idf` |
| Retail — Standalone | `ASHRAE901_RetailStandalone_STD2022_Denver.idf` |
| Retail — Strip Mall | `ASHRAE901_RetailStripmall_STD2022_Denver.idf` |
| School — Primary | `ASHRAE901_SchoolPrimary_STD2022_Denver.idf` |
| School — Secondary | `ASHRAE901_SchoolSecondary_STD2022_Denver.idf` |
| Warehouse | `ASHRAE901_Warehouse_STD2022_Denver.idf` |

---

## 🔧 Module Reference

### `idf_parser.py`
Streams the IDF file line-by-line and returns a `dict[ObjectType, list[fields]]`. Handles multi-line objects, inline `!-` comments, and full-line `!` comments.

### `geometry.py`
Computes zone floor areas and facade (exterior wall) areas from `BuildingSurface:Detailed` vertex data using the cross-product / Shoelace method.

### `extractors.py`
One function per IDF object type. Each returns `{zone_name: normalised_value}` dicts. Handles all EnergyPlus input methods (e.g., `Flow/Zone`, `Flow/Area`, `AirChanges/Hour`).

### `visualizer_adapter.py`
Pure Matplotlib 3D renderer. Parses relative and absolute coordinate systems, renders all surface types (exterior walls, interior walls, roofs, floors, windows) and returns a base64-encoded PNG for direct HTML embedding. Does **not** require `eppy` or EnergyPlus.

### `report_generator.py`
- **Deduplication engine**: Groups zones by base name (stripping `_FLR`, `_ZN`, `_top`, `_bot`, etc.) and collapses identical-load zones. Floor area is intentionally excluded from the comparison criteria.
- **Formatter**: Strips trailing zeros from all numeric values.
- Writes a self-contained dark-themed HTML report.

---

## 📄 License

This project is open source. ASHRAE 90.1 prototype IDF files are provided by the U.S. Department of Energy ([energycodes.gov](https://www.energycodes.gov/prototype-building-models)).
