# Neighbourhood IDF Report Generation

## Checklist
- [x] Create `NUs_parser.py` (or equivalent logic) to read and extract building counts from neighbourhood IDF files.
  - [x] Implement heuristic to identify unique buildings from `Zone` prefixes.
- [x] Create `NUs_report.py` to generate the concise HTML report.
  - [x] Embed axonometric visual (reusing `visualizer_adapter.render_idf_to_base64`).
  - [x] Generate Building Content Summary table with building types and counts.
- [x] Create `NUs_main.py` to orchestrate reading IDFs from `Content/neighbourhoods` and saving HTMLs to `outputs/neighbourhoods`.
  - [x] Ensure folder paths are correctly hardcoded or configurable.
- [x] Test on `Cluster_24_Houses_NEW.idf` and `NEW_Cluster_6_Apartment + ResizedSeconSchool.idf`.
