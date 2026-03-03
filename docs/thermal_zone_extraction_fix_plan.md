# Thermal Zone Extraction Fix Plan

## Issue Description
The user noticed that for the "Small Retail" building, only two thermal zones (`5_ZN_1_FLR_1_SEC_1` and `5_ZN_1_FLR_1_SEC_2`) appeared in the HTML report metadata table, despite the building having 5 zones (4 perimeter zones and 1 core zone). 

## Root Cause
The issue is fundamentally a bug in the `_collapse_rows` function in `report_generator.py`. 
When multiple zones are grouped together by their base name (e.g. `5_ZN_1_FLR_1_SEC`), the code compares their metadata (internal loads, etc., excluding floor area). 

If the zones have differing metadata (like a core zone vs perimeter zone), they form multiple "variants" within the same base name group. However, two bugs occur:
1. **Count is hardcoded to 1**: When re-appending the variants to the final rows, the code has `row["Count"] = 1` instead of `count` from the grouped tuples. This makes the report show `Count: 1` even if the variant represents 4 zones.
2. **Misleading Name**: If there are multiple variants, the code preserves the original name of the *first* zone that triggered the variant (e.g., `5_ZN_1_FLR_1_SEC_1`). This makes the user think ONLY `SEC_1` was extracted, missing the fact that it represents multiple grouped zones.

## Proposed Changes

### `report_generator.py`
#### [MODIFY] `_collapse_rows`
1. Fix the bug where `row["Count"] = 1` is hardcoded. It should be assigned to the actual `count` of that variant.
2. Update the naming logic when `len(unique_variants) > 1`. Instead of keeping the first zone's specific name, we will rename it to `f"{base_name} (Type {chr(65+idx)})"`. This clearly communicates that the row is a sub-type of the base zone group.

```python
        if len(unique_variants) == 1:
            row, count = unique_variants[0]
            row["name"] = base_name
            row["Count"] = count
            final_rows.append(row)
        else:
            for idx, (row, count) in enumerate(unique_variants):
                row["name"] = f"{base_name} (Type {chr(65+idx)})"
                row["Count"] = count
                final_rows.append(row)
```

## Verification Plan
1. Apply the changes to `report_generator.py`.
2. I will use a scratch python script to mock the data dictionary for the 5 zones, run `_collapse_rows` on them, and print the output to ensure the output correctly contains `Count = 4` and `Count = 1` with the `Type A` and `Type B` suffixes.
3. Notify the user of the planned changes.
