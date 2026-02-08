# -*- coding: utf-8 -*-
"""
SuperelliptifyCore.py

Core algorithm for the Superelliptify filter.
Adjusts cubic Bézier curve handle lengths to control superellipticity
(the spectrum from diamond → circle → squircle).

The algorithm uses Bézier circle approximation as its mathematical baseline
and supports an eccentricity-based adjustment that makes more oblong shapes
trend toward squircle-like forms — a property observed across many typefaces.

Algorithm design: Maciej Ratajski
"""

import math


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Bézier circle approximation kappa for a 90° arc: 4/3 * (sqrt(2) - 1)
IOTA = 4.0 / 3.0 * (math.sqrt(2.0) - 1.0)  # ≈ 0.5523

# ---------------------------------------------------------------------------
# Tension presets (in user-facing 0–100 scale)
# ---------------------------------------------------------------------------
# The user sees and types values 0–100.
# Internally these are converted via quadratic mapping: tension = (value/100)²
# This gives finer control near 0 where most typographic values live.

PRESET_CIRCLE = 0.0  # Exact Bézier circle approximation
PRESET_OPTICAL = (
    13.0  # ≈ optically correct circle (internal ≈ 0.017, ≈56% handle length)
)
PRESET_TYPE = 20.0  # Popular in type design (internal = 0.04)
PRESET_SQUIRCLE = 100.0  # Full squircle

# Default values (user-facing 0–100 scale)
DEFAULT_TENSION_DISPLAY = 20.0
DEFAULT_ADJUSTMENT = 50.0  # 0–100 scale, stored and displayed as such


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def get_distance(ax, ay, bx, by):
    """Euclidean distance between two points."""
    return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2)


def get_angle(ax, ay, bx, by):
    """Angle from point A to point B, mapped to [-π, π]."""
    return _map_angle(math.atan2(by - ay, bx - ax))


def _map_angle(angle):
    """Normalize angle to the [-π, π] range."""
    if angle > math.pi:
        angle -= 2.0 * math.pi
    elif angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


def get_tangent_angles(p0x, p0y, p1x, p1y, p2x, p2y, p3x, p3y):
    """
    Compute tangent departure angles for a cubic Bézier segment.

    Given four control points (p0, p1, p2, p3) where p0 and p3 are on-curve
    and p1, p2 are off-curve handles:

    Returns:
        (theta0, theta1) — the angles that each handle makes relative to the
        chord line p0→p3.

    Returns None if angles cannot be computed.
    """
    try:
        angle_AD = get_angle(p0x, p0y, p3x, p3y)
        angle_AB = get_angle(p0x, p0y, p1x, p1y)
        angle_DC = get_angle(p3x, p3y, p2x, p2y)
        theta0 = _map_angle(angle_AB - angle_AD)
        theta1 = _map_angle(math.pi - angle_DC + angle_AD)
        return theta0, theta1
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Display ↔ internal conversion
# ---------------------------------------------------------------------------


def display_to_internal(display_value):
    """
    Convert user-facing tension value (0–100) to internal algorithm value (0–1).
    Uses quadratic mapping: internal = (display / 100)²

    This gives finer control in the low range where most typographic values
    live, while still reaching full squircle at 100.

    Landmarks:
        display   0.0 → internal 0.000  (circle, ≈55% handle length for a 90° arc)
        display  13.0 → internal 0.017  (≈ optical circle, ≈56% handle length for a 90° arc)
        display  20.0 → internal 0.040  (popular in type design)
        display  50.0 → internal 0.250
        display 100.0 → internal 1.000  (squircle)
    """
    normalized = display_value / 100.0
    return normalized * normalized


def internal_to_display(internal_value):
    """
    Convert internal tension value (0–1) back to user-facing value (0–100).
    Inverse of display_to_internal.
    """
    if internal_value < 0.0:
        return 0.0
    return math.sqrt(internal_value) * 100.0


# ---------------------------------------------------------------------------
# Core algorithm
# ---------------------------------------------------------------------------


def compute_handles(
    p0x,
    p0y,
    p1x,
    p1y,
    p2x,
    p2y,
    p3x,
    p3y,
    tension_display=DEFAULT_TENSION_DISPLAY,
    adjustment_display=DEFAULT_ADJUSTMENT,
):
    """
    Compute new off-curve handle positions for a cubic Bézier segment.

    Parameters:
        p0x, p0y: First on-curve point (start of segment)
        p1x, p1y: First off-curve handle
        p2x, p2y: Second off-curve handle
        p3x, p3y: Second on-curve point (end of segment)
        tension_display: Tension in user-facing 0–100 scale.
                         Converted internally via quadratic mapping.
                         0   = circle approximation (≈55% handle length for a 90° arc)
                         13  ≈ more optically correct circle (≈56% handle length for a 90° arc)
                         20  = popular in type design
                         100 = squircle
        adjustment_display: Eccentricity compensation in 0–100 scale.
                            0   = uniform tension for all shapes
                            100 = full compensation (oblong → squircle)

    Returns:
        (new_p1x, new_p1y, new_p2x, new_p2y) or None on error.
    """
    # Convert from display scale to internal
    tension = display_to_internal(tension_display)
    adjustment = adjustment_display / 100.0

    result = get_tangent_angles(p0x, p0y, p1x, p1y, p2x, p2y, p3x, p3y)
    if result is None:
        return None

    theta0, theta1 = result
    alpha = abs(theta0) + abs(theta1)  # total turning angle
    beta = alpha / 2.0  # half-angle

    sin0 = math.sin(theta0)
    cos0 = math.cos(theta0)
    sin1 = math.sin(theta1)
    cos1 = math.cos(theta1)
    sin2 = math.sin(beta)
    cos2 = math.cos(beta)

    # --- Radii (normalized to chord length = 1) ---
    if sin2:
        radius = 1.0 / (2.0 * sin2)
        radius0 = radius * abs(sin1) / abs(sin2)
        radius1 = radius * abs(sin0) / abs(sin2)
    else:
        radius0 = 0.5
        radius1 = 0.5

    # --- Kappa: Bézier circle approximation generalized to angle beta ---
    if sin2:
        kappa = 4.0 / 3.0 * ((1.0 - cos2) / sin2)
    else:
        kappa = 2.0 / 3.0

    # --- Superellipticity modifier ---
    s = tension * (1.0 / IOTA - 1.0)

    # Eccentricity compensation
    eccentricity = abs(sin0 * cos1 - cos0 * sin1)
    maximum = 1.0 / IOTA - 1.0
    s = s + (maximum - s) * eccentricity * adjustment

    # Angle damping: preserves shapes with many on-curve points
    angle_factor = (1.0 - math.cos(alpha)) ** 2
    if angle_factor > 1.0:
        angle_factor = 1.0
    s *= angle_factor

    # Apply modifier to kappa
    kappa = (1.0 + s) * kappa

    # --- Handle lengths ---
    h1 = radius0 * kappa
    h2 = radius1 * kappa

    # --- Transform back to world coordinates ---
    distance_AD = get_distance(p0x, p0y, p3x, p3y)
    angle_AD = get_angle(p0x, p0y, p3x, p3y)

    h1_angle = angle_AD + theta0
    h2_angle = angle_AD - theta1

    new_p1x = p0x + math.cos(h1_angle) * h1 * distance_AD
    new_p1y = p0y + math.sin(h1_angle) * h1 * distance_AD
    new_p2x = p3x - math.cos(h2_angle) * h2 * distance_AD
    new_p2y = p3y - math.sin(h2_angle) * h2 * distance_AD

    return (new_p1x, new_p1y, new_p2x, new_p2y)
