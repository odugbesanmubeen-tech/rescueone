from math import asin, cos, radians, sin, sqrt


def haversine_km(lat1, lng1, lat2, lng2):
    """Great-circle distance between two points in kilometres."""
    lat1, lng1, lat2, lng2 = map(radians, (lat1, lng1, lat2, lng2))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lng2 - lng1) / 2) ** 2
    return 6371.0088 * 2 * asin(sqrt(a))
