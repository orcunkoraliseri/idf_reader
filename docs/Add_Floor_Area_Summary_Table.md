# Add Floor Area Summary Table

The goal is to calculate the total built area, conditioned area, and unconditioned area for the building, and display them in a new summary table directly under the axonometric visual in the HTML report.

## Proposed Changes

### `report_generator.py`
- Add a new helper function `_build_area_summary_html(zone_data: list[dict], hvac_data: dict) -> str` to handle the calculations and HTML building.
- Calculate values:
  - **Total Built Area**: Sum of `floor_area` across all entries in `zone_data` before deduplication.
  - **Total Unconditioned Area**: Sum of `floor_area` for zones where `hvac_data.get(zone["name"], {}).get("template", "Unconditioned") == "Unconditioned"`.
  - **Total Conditioned Area**: Sum of `floor_area` for zones where the template is something other than "Unconditioned".
- Format these calculated areas into an HTML snippet (card style).
- Update the signature of `generate_html_content` to accept the new `area_summary_html` variable.
- Modify `generate_reports` to call the helper function and pass the html into `generate_html_content`.
- Within the HTML string returned by `generate_html_content`, insert `{area_summary_html}` immediately following `{viz_html}`.

## Verification Plan

### Automated Verification
- Run `main.py` on the `ASHRAE901_OfficeSmall_STD2022_Denver.idf` and `TwoStoreyHouse_V242.idf` files.
- Ensure the sum of Conditioned and Unconditioned areas exactly matches the Total Built Area.
- Check the output HTML to confirm the new table appears directly beneath the "3D Building Geometry" card.
