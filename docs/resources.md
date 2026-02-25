# Resources

## EnergyPlus Prototype Building Models
The IDF files used in this project are based on the DOE/ASHRAE Prototype Building Models.

- **URL**: [https://www.energycodes.gov/prototype-building-models](https://www.energycodes.gov/prototype-building-models)
- **Modeling Distinction**:
  - **ASHRAE 90.1**: Always used for commercial mid-rise and high-rise buildings.
  - **IECC**: Always used for low-rise residential and commercial buildings.
- **Handling Unknowns & Equivalents**: 
  - If a thermal zone's DCV or Economizer status does not parse cleanly or appears as an anomaly, the URL above serves as the source-of-truth reference.
  - The agent is instructed to cross-reference similar files or download equivalents from this link if any discrepancies occur or if prototype defaults (like Hospital ER/OR fixed outdoor-air without DCV) seem confusing.

## Local Data
The prototype models are stored in the `Content/` directory.
