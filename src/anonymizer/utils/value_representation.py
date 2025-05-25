import logging
from typing import Any

from pydicom import Sequence
from pydicom.datadict import dictionary_VR
from pydicom.tag import Tag, BaseTag

logger = logging.getLogger(__name__)

def get_python_type_for_vr(vr: str) -> type:
    """
    Map a DICOM VR to its expected Python type.

    Args:
        vr (str): DICOM Value Representation (e.g., 'LO', 'SQ').

    Returns:
        Type: The corresponding Python type as a callable type.

    Notes:
        - VR to datatype are taken from https://pydicom.github.io/pydicom/dev/guides/element_value_types.html (last access May 23rd 2025)
        - if VR is unknown falls back to empty strings
    """
    vr = vr.upper()

    vr_type_map = {
        "AE": str,
        "AS": str,
        "AT": int,  # represented as BaseTag but int works for Tag in input
        "CS": str,
        "DA": str,  # can also be DA, but input usually as string
        "DS": float,  # DSfloat or DSdecimal
        "DT": str,  # or DT
        "FL": float,
        "FD": float,
        "IS": int,  # internally IS
        "LO": str,
        "LT": str,
        "OB": bytes,
        "OD": bytes,
        "OF": bytes,
        "OL": bytes,
        "OV": bytes,
        "OW": bytes,
        "PN": str,  # or PersonName
        "SH": str,
        "SL": int,
        "SQ": Sequence,
        "SS": int,
        "ST": str,
        "SV": int,
        "TM": str,
        "UC": str,
        "UI": str,  # or UID
        "UL": int,
        "UN": bytes,
        "UR": str,
        "US": int,
        "UT": str,
        "UV": int,
    }

    py_type = vr_type_map.get(vr)

    if py_type is None:
        logger.warning(f"Unknown Value Representation '{vr}' encountered — defaulting to str.")
        return str

    return py_type

def create_empty_value_for_vr(vr: str) -> Any:
    """
    Create an appropriate empty value for a given DICOM Value Representation (VR).

    Args:
        vr (str): The DICOM VR (e.g., "LO", "SQ").

    Returns:
        Any: An empty value appropriate for the VR.
    """
    py_type = get_python_type_for_vr(vr)

    if py_type is str:
        return ""
    if py_type is int or py_type is float:
        return None
    if py_type is bytes:
        return b""
    if py_type is Sequence:
        return Sequence()

    logger.warning(f"Unable to determine empty value for VR '{vr}' — using empty string as fallback.")
    return ""

def get_vr_and_empty_value(tag_str: str | BaseTag) -> tuple[str, object]:
    """
    Determines the appropriate Value Representation (VR) and an empty value for this VR.

    Args:
        tag (str): DICOM tag to resolve.

    Returns:
        tuple[str, object]: A tuple of (VR, empty_value).
    """
    tag = Tag(tag_str)
    if tag.is_private:
        logger.warning(f"Tag {tag} is private — using default Value Representation 'LO'")
        return "LO", ""
    try:
        vr = dictionary_VR(tag)
    except KeyError as e:
        logger.warning(f"Value Representation lookup failed for tag {tag}: {e}. Defaulting to 'LO'")
        vr = "LO"

    empty_value = create_empty_value_for_vr(vr)
    return vr, empty_value

def convert_to_compatible_vr(value: Any, vr: str) -> object:
    """
    Converts the value to the appropriate python type for a given DICOM VR.

    Args:
        value (Any): The input value.
        vr (str): The DICOM Value Representation.

    Returns:
        object: Value converted to a VR-compatible type.
    """
    py_type = get_python_type_for_vr(vr)

    try:
        if py_type is Sequence:
            return value if isinstance(value, Sequence) else Sequence([value])
        return py_type(value)
    except Exception as e:
        logger.warning(f"Failed to convert value '{value}' to type '{py_type}' for VR '{vr}': {e}")
        return create_empty_value_for_vr(vr)