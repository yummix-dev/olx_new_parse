# This file makes parse directory a Python package
# Import subclasses to register them in BaseParser.registry
from parse.parse_apartment import ApartmentParse

__all__ = ["ApartmentParse"]
