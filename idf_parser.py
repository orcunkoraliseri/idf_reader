"""
IDF Parser Module for EnergyPlus Input Data Files.

This module provides functionality to read and tokenize EnergyPlus .idf files,
extracting object types and their associated field values while ignoring
comments and normalizing whitespace.
"""

import os
import re


def parse_idf(file_path: str) -> dict[str, list[list[str]]]:
    """Parses an EnergyPlus IDF file into a dictionary of objects.

    Args:
        file_path: Absolute path to the .idf file.

    Returns:
        A dictionary where keys are object types (uppercase) and values are
        lists of objects. Each object is a list of its field values (strings).

    Raises:
        FileNotFoundError: If the specified file_path does not exist.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"IDF file not found: {file_path}")

    idf_data: dict[str, list[list[str]]] = {}

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # Remove all comments (starting with ! until the end of the line)
    content = re.sub(r"!.*", "", content)

    # Split by semicolon to identify individual EnergyPlus objects
    # Note: semicolon is the object terminator in EnergyPlus IDF syntax
    raw_objects = content.split(";")

    for obj in raw_objects:
        clean_obj = obj.strip()
        if not clean_obj:
            continue

        # Split by comma to extract fields within the object
        # The first field is always the Object Type
        fields = [f.strip() for f in clean_obj.split(",")]
        if not fields:
            continue

        obj_type = fields[0].upper()
        # Some objects might have no fields other than the type, but usually they do
        obj_values = fields[1:] if len(fields) > 1 else []

        if obj_type not in idf_data:
            idf_data[obj_type] = []

        idf_data[obj_type].append(obj_values)

    return idf_data
