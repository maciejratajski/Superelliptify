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

# Guard against degenerate zero-length handles in preserve mode
EPSILON = 1e-6

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

# Distribution modes
DISTRIBUTION_BALANCED = "balanced"
DISTRIBUTION_PRESERVE = "preserve"
DISTRIBUTION_SMOOTH = "smooth"
DISTRIBUTION_SMART = "smart"
DEFAULT_DISTRIBUTION = DISTRIBUTION_BALANCED


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


# ---------------------------------------------------------------------------
# Handle redistribution (preserve mode)
# ---------------------------------------------------------------------------


def _area_coefficients(x0, y0, x3, y3, ux1, uy1, ux2, uy2):
    """
    Compute coefficients for the area as a function of handle lengths.

    With P1 = P0 + h1 * u1 and P2 = P3 + h2 * u2 (handles along fixed
    unit directions u1, u2), the signed area becomes:

        A(h1, h2) = c0 + c1 * h1 + c2 * h2 + c12 * h1 * h2

    Returns (c0, c1, c2, c12).
    """
    c0 = (x0 * y3 - x3 * y0) / 2.0
    c1 = 6.0 * (ux1 * (y3 - y0) - uy1 * (x3 - x0)) / 20.0
    c2 = 6.0 * (ux2 * (y3 - y0) - uy2 * (x3 - x0)) / 20.0
    c12 = 3.0 * (ux1 * uy2 - ux2 * uy1) / 20.0
    return c0, c1, c2, c12


def _solve_h2_for_ratio(c0, c1, c2, c12, A_target, r, h2_bal):
    """
    Given area constraint A(r*h2, h2) = A_target, solve for h2.

    This is a quadratic in h2:
        c12 * r * h2² + (c1 * r + c2) * h2 + (c0 - A_target) = 0

    Returns h2 > 0 closest to h2_bal, or None if no valid solution.
    """
    a = c12 * r
    b = c1 * r + c2
    c = c0 - A_target

    if abs(a) < 1e-12:
        # Linear case
        if abs(b) < 1e-12:
            return None
        h2 = -c / b
        return h2 if h2 > EPSILON else None

    disc = b * b - 4.0 * a * c
    if disc < 0.0:
        return None

    sqrt_disc = math.sqrt(disc)
    h2_a = (-b + sqrt_disc) / (2.0 * a)
    h2_b = (-b - sqrt_disc) / (2.0 * a)

    candidates = [h for h in (h2_a, h2_b) if h > EPSILON]
    if not candidates:
        return None
    return min(candidates, key=lambda h: abs(h - h2_bal))


def redistribute_handles(
    p0x, p0y,
    p1_orig_x, p1_orig_y,
    p2_orig_x, p2_orig_y,
    p1_bal_x, p1_bal_y,
    p2_bal_x, p2_bal_y,
    p3x, p3y,
):
    """
    Redistribute balanced handles to restore the original handle-length ratio
    while preserving the Bézier curve's signed area (Green's theorem).

    This is a post-processing step applied after compute_handles().

    The target ratio is measured in triangle-side percentages (Curve Equalizer
    convention) so that only the designer's deliberate imbalance is restored,
    not the geometric asymmetry already accounted for by the balanced algorithm.

    With fixed endpoints and fixed tangent directions the signed area is
    bilinear in (h1, h2), so imposing the target ratio h1 = r * h2 together
    with the area constraint yields a single quadratic in h2 — solved in O(1).

    Parameters:
        p0x, p0y:               Start on-curve point (fixed)
        p1_orig_x, p1_orig_y:   Original first handle (before superelliptify)
        p2_orig_x, p2_orig_y:   Original second handle (before superelliptify)
        p1_bal_x, p1_bal_y:     Balanced first handle (from compute_handles)
        p2_bal_x, p2_bal_y:     Balanced second handle (from compute_handles)
        p3x, p3y:               End on-curve point (fixed)

    Returns:
        (new_p1x, new_p1y, new_p2x, new_p2y) with the original triangle-%
        ratio restored, or the balanced result if no valid solution exists.
    """
    # Handle directions from balanced result (these define the tangent lines)
    dx1 = p1_bal_x - p0x
    dy1 = p1_bal_y - p0y
    h1_bal = math.sqrt(dx1 * dx1 + dy1 * dy1)

    dx2 = p2_bal_x - p3x
    dy2 = p2_bal_y - p3y
    h2_bal = math.sqrt(dx2 * dx2 + dy2 * dy2)

    if h1_bal < EPSILON or h2_bal < EPSILON:
        return (p1_bal_x, p1_bal_y, p2_bal_x, p2_bal_y)

    # Unit direction vectors
    ux1 = dx1 / h1_bal
    uy1 = dy1 / h1_bal
    ux2 = dx2 / h2_bal
    uy2 = dy2 / h2_bal

    # Original handle lengths
    ox1 = p1_orig_x - p0x
    oy1 = p1_orig_y - p0y
    h1_orig = math.sqrt(ox1 * ox1 + oy1 * oy1)

    ox2 = p2_orig_x - p3x
    oy2 = p2_orig_y - p3y
    h2_orig = math.sqrt(ox2 * ox2 + oy2 * oy2)

    if h1_orig < EPSILON or h2_orig < EPSILON:
        return (p1_bal_x, p1_bal_y, p2_bal_x, p2_bal_y)

    r_bal = h1_bal / h2_bal
    r_orig = h1_orig / h2_orig

    # Triangle-percentage ratio: how much the designer deviated from balanced.
    # balanced mode gives pct0 == pct1 (uniform kappa), so r_bal already
    # encodes the geometric asymmetry.  Dividing it out isolates the
    # designer's deliberate choice.
    pct_ratio_orig = r_orig / r_bal

    # Skip if the original was already balanced (in triangle-% terms)
    if abs(pct_ratio_orig - 1.0) < EPSILON:
        return (p1_bal_x, p1_bal_y, p2_bal_x, p2_bal_y)

    # Target raw ratio that reproduces the same triangle-% imbalance
    r_target = pct_ratio_orig * r_bal

    # Area coefficients and balanced area
    c0, c1, c2, c12 = _area_coefficients(x0=p0x, y0=p0y, x3=p3x, y3=p3y,
                                          ux1=ux1, uy1=uy1, ux2=ux2, uy2=uy2)
    A_bal = c0 + c1 * h1_bal + c2 * h2_bal + c12 * h1_bal * h2_bal

    # Solve: area(r_target * h2, h2) = A_bal  →  quadratic in h2
    h2_new = _solve_h2_for_ratio(c0, c1, c2, c12, A_bal, r_target, h2_bal)
    if h2_new is None:
        return (p1_bal_x, p1_bal_y, p2_bal_x, p2_bal_y)

    h1_new = r_target * h2_new

    return (
        p0x + ux1 * h1_new,
        p0y + uy1 * h1_new,
        p3x + ux2 * h2_new,
        p3y + uy2 * h2_new,
    )


# ---------------------------------------------------------------------------
# G2 curvature harmonization (smooth mode)
# ---------------------------------------------------------------------------


def _line_intersection(x1, y1, x2, y2, x3, y3, x4, y4):
    """
    Intersection of lines (x1,y1)-(x2,y2) and (x3,y3)-(x4,y4).
    Returns (px, py) or None if lines are parallel.
    """
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < EPSILON:
        return None
    cross12 = x1 * y2 - y1 * x2
    cross34 = x3 * y4 - y3 * x4
    px = (cross12 * (x3 - x4) - (x1 - x2) * cross34) / denom
    py = (cross12 * (y3 - y4) - (y1 - y2) * cross34) / denom
    return px, py


def _segment_intersection(p0x, p0y, p1x, p1y, p2x, p2y, p3x, p3y):
    """
    Intersection of the two handle lines of a cubic Bézier segment.

    Line 1: through P0 and P1 (start on-curve → first handle).
    Line 2: through P3 and P2 (end on-curve → second handle).

    Uses triangle-area test to verify the intersection is on the correct
    side of the curve (both handles point toward it).

    Returns (ix, iy) or None if parallel or on the wrong side.
    """
    # Slope-based intersection (handles vertical lines cleanly)
    dx_ab = p1x - p0x
    dx_cd = p2x - p3x

    if abs(dx_ab) > EPSILON:
        slope_ab = (p1y - p0y) / dx_ab
    else:
        slope_ab = None  # vertical

    if abs(dx_cd) > EPSILON:
        slope_cd = (p2y - p3y) / dx_cd
    else:
        slope_cd = None  # vertical

    # Parallel or coincident
    if slope_ab == slope_cd:
        return None
    if slope_ab is not None and slope_cd is not None:
        if abs(slope_ab - slope_cd) < EPSILON:
            return None

    # Compute intersection
    if slope_ab is None:
        x = p0x
        y = slope_cd * (x - p3x) + p3y
    elif slope_cd is None:
        x = p3x
        y = slope_ab * (x - p0x) + p0y
    else:
        x = (slope_ab * p0x - p0y - slope_cd * p3x + p3y) / (slope_ab - slope_cd)
        y = slope_ab * (x - p0x) + p0y

    # Triangle-area test: intersection must be on the correct side
    # Area(P0, P2, P1) and Area(P0, P2, P3) and Area(P0, P2, I)
    # must all have the same sign
    def _tri_area(ax, ay, bx, by, cx, cy):
        return (bx - ax) * (cy - ay) - (cx - ax) * (by - ay)

    area_adb = _tri_area(p0x, p0y, p2x, p2y, p1x, p1y)
    area_adc = _tri_area(p0x, p0y, p2x, p2y, p3x, p3y)
    area_adi = _tri_area(p0x, p0y, p2x, p2y, x, y)

    if (area_adb > 0 and area_adc > 0 and area_adi > 0):
        return (x, y)
    elif (area_adb < 0 and area_adc < 0 and area_adi < 0):
        return (x, y)
    else:
        return None


def smooth_handles_at_node(
    p0ax, p0ay,
    a1x, a1y,
    a2x, a2y,
    nx, ny,
    b1x, b1y,
    b2x, b2y,
    p3bx, p3by,
):
    """
    Adjust handles at a smooth node to achieve G2 curvature continuity.

    Uses a direct curvature-matching approach:

    The curvature at the node from each segment depends on:
      κ = 2·d_far⊥ / (3·L_near²)
    where d_far⊥ is the normal displacement of the far handle from the
    tangent line, and L_near is the near-handle length from the node.

    The G2 condition κ_A = κ_B gives:
      L_b / L_a = √(d_b⊥ / d_a⊥)  =  ρ

    We find the optimal L_a that minimizes normalized deviation from
    the balanced handle lengths, then clamp both handles simultaneously
    against their segment intersection limits.

    Parameters:
        p0ax, p0ay: Start on-curve of segment A (far on-curve, incoming)
        a1x, a1y:   Far handle of segment A (first off-curve of seg A)
        a2x, a2y:   Near handle of segment A (adjacent to the node)
        nx, ny:     The smooth on-curve node
        b1x, b1y:   Near handle of segment B (adjacent to the node)
        b2x, b2y:   Far handle of segment B (second off-curve of seg B)
        p3bx, p3by: End on-curve of segment B (far on-curve, outgoing)

    Returns:
        (new_a2x, new_a2y, new_b1x, new_b1y)
    """
    # Handle directions (unit vectors from node toward each handle)
    da2x = a2x - nx
    da2y = a2y - ny
    La_bal = math.sqrt(da2x * da2x + da2y * da2y)

    db1x = b1x - nx
    db1y = b1y - ny
    Lb_bal = math.sqrt(db1x * db1x + db1y * db1y)

    if La_bal < EPSILON or Lb_bal < EPSILON:
        return (a2x, a2y, b1x, b1y)

    # Unit direction vectors from node toward each near-handle
    ua_x = da2x / La_bal
    ua_y = da2y / La_bal
    ub_x = db1x / Lb_bal
    ub_y = db1y / Lb_bal

    # Tangent direction at the node.
    # For segment A ending at node: tangent points from a2 toward node,
    # i.e., opposite to ua.  For segment B starting at node: tangent
    # points from node toward b1, i.e., along ub.
    # For a smooth node, ua ≈ -ub (collinear, opposite sides).
    # We use ub as the tangent direction (the "forward" direction).
    tx = ub_x
    ty = ub_y

    # Normal vector (90° CCW rotation of tangent)
    norm_x = -ty
    norm_y = tx

    # Normal displacement of the far handles from the node.
    # d_a⊥ = signed projection of (a1 - node) onto the normal.
    # d_b⊥ = signed projection of (b2 - node) onto the normal.
    vec_a1_x = a1x - nx
    vec_a1_y = a1y - ny
    d_a_perp = vec_a1_x * norm_x + vec_a1_y * norm_y

    vec_b2_x = b2x - nx
    vec_b2_y = b2y - ny
    d_b_perp = vec_b2_x * norm_x + vec_b2_y * norm_y

    # For G2 continuity, both curvatures must match in sign.
    # If d_a⊥ and d_b⊥ have opposite signs, the curvature centers
    # are on opposite sides (inflection at node) — fall back to balanced.
    if abs(d_a_perp) < EPSILON or abs(d_b_perp) < EPSILON:
        return (a2x, a2y, b1x, b1y)
    if (d_a_perp > 0) != (d_b_perp > 0):
        # Curvature centers on opposite sides — G2 not achievable
        return (a2x, a2y, b1x, b1y)

    # G2 ratio: L_b = ρ · L_a
    rho = math.sqrt(abs(d_b_perp) / abs(d_a_perp))

    # ------------------------------------------------------------------
    # Compute clamping limits from segment intersections.
    # ------------------------------------------------------------------

    # Segment A: (p0a, a1, a2, node) — max length for the a2 handle
    La_max = None
    seg_a_int = _segment_intersection(
        p0ax, p0ay, a1x, a1y, a2x, a2y, nx, ny)
    if seg_a_int is not None:
        La_max = get_distance(nx, ny, seg_a_int[0], seg_a_int[1])

    # Segment B: (node, b1, b2, p3b) — max length for the b1 handle
    Lb_max = None
    seg_b_int = _segment_intersection(
        nx, ny, b1x, b1y, b2x, b2y, p3bx, p3by)
    if seg_b_int is not None:
        Lb_max = get_distance(nx, ny, seg_b_int[0], seg_b_int[1])

    # ------------------------------------------------------------------
    # Find optimal L_a using normalized least-squares.
    #
    # Minimize: ((La - La_bal)/La_bal)² + ((ρ·La - Lb_bal)/Lb_bal)²
    #
    # Solution:
    #   La_opt = La_bal·Lb_bal·(Lb_bal + ρ·La_bal)
    #            / (Lb_bal² + ρ²·La_bal²)
    # ------------------------------------------------------------------
    rho2 = rho * rho
    numer = La_bal * Lb_bal * (Lb_bal + rho * La_bal)
    denom = Lb_bal * Lb_bal + rho2 * La_bal * La_bal
    if abs(denom) < EPSILON:
        return (a2x, a2y, b1x, b1y)
    La_opt = numer / denom

    # Clamp: La ≤ La_max and ρ·La ≤ Lb_max
    La_final = La_opt
    if La_max is not None and La_final > La_max:
        La_final = La_max
    if Lb_max is not None and rho > EPSILON and La_final > Lb_max / rho:
        La_final = Lb_max / rho

    # Ensure we don't go below zero
    if La_final < EPSILON:
        return (a2x, a2y, b1x, b1y)

    Lb_final = rho * La_final

    # ------------------------------------------------------------------
    # Compute new handle positions along their original directions.
    # ------------------------------------------------------------------
    new_a2x = nx + ua_x * La_final
    new_a2y = ny + ua_y * La_final
    new_b1x = nx + ub_x * Lb_final
    new_b1y = ny + ub_y * Lb_final

    return (new_a2x, new_a2y, new_b1x, new_b1y)


# ---------------------------------------------------------------------------
# Smart mode: G2 continuity by moving on-curve nodes
#
# The node-positioning algorithm used here is based on the harmonization
# method described by Simon Cozens and implemented in the Green Harmony
# plugin by Alex Slobzheninov and Rainer Erich Scheichelbauer (Apache-2.0).
# See: https://gist.github.com/simoncozens/3c5d304ae2c14894393c6284df91be5b
# See: https://github.com/mekkablue/GreenHarmony
# ---------------------------------------------------------------------------


def smart_node_position(
    p0ax, p0ay,
    a1x, a1y,
    a2x, a2y,
    nx, ny,
    b1x, b1y,
    b2x, b2y,
    p3bx, p3by,
):
    """
    Compute a new on-curve node position that achieves G2 curvature
    continuity, while preserving all handle (off-curve) positions exactly.

    Moves the node along the line between its two adjacent (near) handles
    a2 and b1 to the position where curvature from each side matches.

    Based on the harmonization algorithm by Simon Cozens, as implemented
    in Green Harmony by Alex Slobzheninov and Rainer Erich Scheichelbauer.

    The algorithm finds the intersection of the two far-handle lines,
    computes the geometric mean ratio, and places the node at the
    G2-optimal position on the line segment between a2 and b1.

    Parameters:
        p0ax, p0ay: Start on-curve of segment A (far on-curve, incoming)
        a1x, a1y:   Far handle of segment A
        a2x, a2y:   Near handle of segment A (adjacent to the node)
        nx, ny:     Current on-curve node position
        b1x, b1y:   Near handle of segment B (adjacent to the node)
        b2x, b2y:   Far handle of segment B
        p3bx, p3by: End on-curve of segment B (far on-curve, outgoing)

    Returns:
        (new_nx, new_ny) or (nx, ny) if no valid solution.
    """
    # Distance between the two near-handles — if they coincide, no room
    # to move the node.
    dist_a2_b1 = get_distance(a2x, a2y, b1x, b1y)
    if dist_a2_b1 < EPSILON:
        return (nx, ny)

    # Far-handle line of segment B: through b1 and b2 (extended)
    # Far-handle line of segment A: through a2 and a1 (extended)
    inter = _line_intersection(b1x, b1y, b2x, b2y, a2x, a2y, a1x, a1y)
    if inter is None:
        return (nx, ny)

    ix, iy = inter

    # Distances for the ratio computation (Green Harmony formula):
    # r0 = dist(far_B, near_B) / dist(near_B, intersection)
    # r1 = dist(intersection, near_A) / dist(near_A, far_A)
    dist_b2_b1 = get_distance(b2x, b2y, b1x, b1y)
    dist_b1_I = get_distance(b1x, b1y, ix, iy)
    dist_I_a2 = get_distance(ix, iy, a2x, a2y)
    dist_a2_a1 = get_distance(a2x, a2y, a1x, a1y)

    if dist_b1_I < EPSILON or dist_a2_a1 < EPSILON:
        return (nx, ny)

    r0 = dist_b2_b1 / dist_b1_I
    r1 = dist_I_a2 / dist_a2_a1
    ratio = math.sqrt(r0 * r1)

    # t parameter: position on the line from b1 to a2
    # t=0 → at b1, t=1 → at a2
    t = ratio / (ratio + 1.0)

    # Clamp t to avoid degenerate handles (node too close to either handle)
    MIN_T = 0.05
    MAX_T = 0.95
    t = max(MIN_T, min(MAX_T, t))

    # New node position: lerp from b1 to a2
    new_nx = b1x + t * (a2x - b1x)
    new_ny = b1y + t * (a2y - b1y)

    return (new_nx, new_ny)
