import colorsys
from typing import Tuple
from config import COLOR_THRESHOLDS

def hue_sat_to_xy(hue: int, sat: int) -> Tuple[float, float]:
    h = hue / 65535.0
    s = sat / 254.0
    r, g, b = colorsys.hsv_to_rgb(h, s, 1.0)
    
    def gamma(c):
        return ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92
    
    R, G, B = gamma(r), gamma(g), gamma(b)
    X = R * 0.664511 + G * 0.154324 + B * 0.162028
    Y = R * 0.283881 + G * 0.668433 + B * 0.047685
    Z = R * 0.000088 + G * 0.072310 + B * 0.986039
    
    sum_xyz = X + Y + Z
    if sum_xyz == 0:
        return 0.0, 0.0
    return round(X / sum_xyz, 4), round(Y / sum_xyz, 4)

def get_color_name(hue: int) -> str:
    """Approximate mapping from hue value (0-65535) to a human-readable color name."""
    for limit, name in COLOR_THRESHOLDS:
        if hue < limit:
            return name
    return "Red"
