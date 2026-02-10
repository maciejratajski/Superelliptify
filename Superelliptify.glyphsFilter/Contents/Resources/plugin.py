# -*- coding: utf-8 -*-
"""
Superelliptify — A Glyphs 3 Filter Plugin

Adjusts cubic Bézier curve handle lengths along the diamond → circle → squircle
spectrum, with eccentricity-aware adjustment for oblong shapes.
"""

import objc
import os
import sys

from GlyphsApp import Glyphs, CURVE, OFFCURVE
from GlyphsApp.plugins import FilterWithDialog
from vanilla import CheckBox, Group, Slider, TextBox, EditText, SquareButton, Window

# Import core algorithm from sibling module
plugin_dir = os.path.dirname(__file__)
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)
from SuperelliptifyCore import (
    compute_handles,
    redistribute_handles,
    smooth_handles_at_node,
    smart_node_position,
    PRESET_CIRCLE,
    PRESET_OPTICAL,
    PRESET_TYPE,
    PRESET_SQUIRCLE,
    DEFAULT_TENSION_DISPLAY,
    DEFAULT_ADJUSTMENT,
    DEFAULT_DISTRIBUTION,
    DISTRIBUTION_BALANCED,
    DISTRIBUTION_PRESERVE,
    DISTRIBUTION_SMOOTH,
    DISTRIBUTION_SMART,
)

# Glyphs.defaults keys
TENSION_KEY = "com.superelliptify.tension"
ADJUSTMENT_KEY = "com.superelliptify.adjustment"
DISTRIBUTION_KEY = "com.superelliptify.distribution"


class Superelliptify(FilterWithDialog):

    dialog = objc.IBOutlet()

    @objc.python_method
    def settings(self):
        self.menuName = Glyphs.localize({
            "en": "Superelliptify",
        })
        self.actionButtonLabel = Glyphs.localize({
            "en": "Apply",
        })

        # Build vanilla UI
        labelW = 80       # wide enough for "Distribution:"
        ctrlX = 88        # left edge of controls (after label column)
        width = 290
        height = 155

        self.paletteView = Window((width, height))
        self.paletteView.group = Group((0, 0, width, height))

        # --- Preset buttons row ---
        y = 8
        buttonW = 46
        gap = 3
        x = ctrlX
        self.paletteView.group.presetCircle = SquareButton(
            (x, y, buttonW, 18),
            "Circle",
            callback=self.presetCircleCallback_,
            sizeStyle="mini",
        )
        x += buttonW + gap
        self.paletteView.group.presetOptical = SquareButton(
            (x, y, buttonW, 18),
            "Optical",
            callback=self.presetOpticalCallback_,
            sizeStyle="mini",
        )
        x += buttonW + gap
        self.paletteView.group.presetType = SquareButton(
            (x, y, buttonW, 18),
            "Type",
            callback=self.presetTypeCallback_,
            sizeStyle="mini",
        )
        x += buttonW + gap
        self.paletteView.group.presetSquircle = SquareButton(
            (x, y, -8, 18),
            "Squircle",
            callback=self.presetSquircleCallback_,
            sizeStyle="mini",
        )

        # --- Tension slider row (label on this row) ---
        y = 33
        self.paletteView.group.tensionLabel = TextBox(
            (10, y + 1, labelW, 17),
            "Tension:",
            sizeStyle="small",
        )
        self.paletteView.group.tensionSlider = Slider(
            (ctrlX, y, -58, 17),
            minValue=0.0,
            maxValue=100.0,
            value=DEFAULT_TENSION_DISPLAY,
            callback=self.tensionSliderCallback_,
            continuous=True,
            sizeStyle="small",
        )
        self.paletteView.group.tensionField = EditText(
            (-52, y - 1, -8, 19),
            text=self._format_value(DEFAULT_TENSION_DISPLAY),
            callback=self.tensionFieldCallback_,
            sizeStyle="small",
        )

        # --- Adjustment slider row ---
        y = 60
        self.paletteView.group.adjustmentLabel = TextBox(
            (10, y + 1, labelW, 17),
            "Adjustment:",
            sizeStyle="small",
        )
        self.paletteView.group.adjustmentSlider = Slider(
            (ctrlX, y, -58, 17),
            minValue=0.0,
            maxValue=100.0,
            value=DEFAULT_ADJUSTMENT,
            callback=self.adjustmentSliderCallback_,
            continuous=True,
            sizeStyle="small",
        )
        self.paletteView.group.adjustmentField = EditText(
            (-52, y - 1, -8, 19),
            text=self._format_value(DEFAULT_ADJUSTMENT),
            callback=self.adjustmentFieldCallback_,
            sizeStyle="small",
        )

        # --- Distribution mode rows (two lines) ---
        y = 87
        self.paletteView.group.distributionLabel = TextBox(
            (10, y + 1, labelW, 17),
            "Distribution:",
            sizeStyle="small",
        )
        self.paletteView.group.distributionBalanced = CheckBox(
            (ctrlX, y, 75, 18),
            "Balanced",
            callback=self.distributionBalancedCallback_,
            sizeStyle="small",
            value=True,
        )
        self.paletteView.group.distributionPreserve = CheckBox(
            (ctrlX + 75, y, -8, 18),
            "Preserve",
            callback=self.distributionPreserveCallback_,
            sizeStyle="small",
            value=False,
        )
        y = 107
        self.paletteView.group.distributionSmooth = CheckBox(
            (ctrlX, y, 75, 18),
            "Smooth",
            callback=self.distributionSmoothCallback_,
            sizeStyle="small",
            value=False,
        )
        self.paletteView.group.distributionSmart = CheckBox(
            (ctrlX + 75, y, -8, 18),
            "Smart",
            callback=self.distributionSmartCallback_,
            sizeStyle="small",
            value=False,
        )

        # --- Preview checkbox (bottom left, always defaults to checked) ---
        y = 133
        self.paletteView.group.previewCheckbox = CheckBox(
            (10, y, 80, 18),
            "Preview",
            callback=self.previewCallback_,
            sizeStyle="small",
            value=True,
        )

        # Expose vanilla view as the Glyphs dialog
        self.dialog = self.paletteView.group.getNSView()

    @objc.python_method
    def start(self):
        Glyphs.registerDefault(TENSION_KEY, DEFAULT_TENSION_DISPLAY)
        Glyphs.registerDefault(ADJUSTMENT_KEY, DEFAULT_ADJUSTMENT)
        Glyphs.registerDefault(DISTRIBUTION_KEY, DEFAULT_DISTRIBUTION)
        # Restore saved values to UI
        tension = float(Glyphs.defaults[TENSION_KEY])
        adjustment = float(Glyphs.defaults[ADJUSTMENT_KEY])
        distribution = str(Glyphs.defaults[DISTRIBUTION_KEY])
        self._set_tension_ui(tension)
        self._set_adjustment_ui(adjustment)
        self._set_distribution_ui(distribution)

    # -------------------------------------------------------------------
    # Preset callbacks
    # -------------------------------------------------------------------

    @objc.python_method
    def presetCircleCallback_(self, sender):
        self._apply_tension_preset(PRESET_CIRCLE)

    @objc.python_method
    def presetOpticalCallback_(self, sender):
        self._apply_tension_preset(PRESET_OPTICAL)

    @objc.python_method
    def presetTypeCallback_(self, sender):
        self._apply_tension_preset(PRESET_TYPE)

    @objc.python_method
    def presetSquircleCallback_(self, sender):
        self._apply_tension_preset(PRESET_SQUIRCLE)

    @objc.python_method
    def _apply_tension_preset(self, value):
        Glyphs.defaults[TENSION_KEY] = value
        self._set_tension_ui(value)
        self.update()

    # -------------------------------------------------------------------
    # Slider / field callbacks
    # -------------------------------------------------------------------

    @objc.python_method
    def tensionSliderCallback_(self, sender):
        value = sender.get()
        Glyphs.defaults[TENSION_KEY] = value
        self.paletteView.group.tensionField.set(self._format_value(value))
        self.update()

    @objc.python_method
    def tensionFieldCallback_(self, sender):
        try:
            value = float(sender.get())
        except (ValueError, TypeError):
            return
        value = max(0.0, min(100.0, value))
        Glyphs.defaults[TENSION_KEY] = value
        self.paletteView.group.tensionSlider.set(value)
        self.update()

    @objc.python_method
    def adjustmentSliderCallback_(self, sender):
        value = sender.get()
        Glyphs.defaults[ADJUSTMENT_KEY] = value
        self.paletteView.group.adjustmentField.set(self._format_value(value))
        self.update()

    @objc.python_method
    def adjustmentFieldCallback_(self, sender):
        try:
            value = float(sender.get())
        except (ValueError, TypeError):
            return
        value = max(0.0, min(100.0, value))
        Glyphs.defaults[ADJUSTMENT_KEY] = value
        self.paletteView.group.adjustmentSlider.set(value)
        self.update()

    # -------------------------------------------------------------------
    # Distribution callbacks
    # -------------------------------------------------------------------

    @objc.python_method
    def distributionBalancedCallback_(self, sender):
        Glyphs.defaults[DISTRIBUTION_KEY] = DISTRIBUTION_BALANCED
        self._set_distribution_ui(DISTRIBUTION_BALANCED)
        self.update()

    @objc.python_method
    def distributionPreserveCallback_(self, sender):
        Glyphs.defaults[DISTRIBUTION_KEY] = DISTRIBUTION_PRESERVE
        self._set_distribution_ui(DISTRIBUTION_PRESERVE)
        self.update()

    @objc.python_method
    def distributionSmoothCallback_(self, sender):
        Glyphs.defaults[DISTRIBUTION_KEY] = DISTRIBUTION_SMOOTH
        self._set_distribution_ui(DISTRIBUTION_SMOOTH)
        self.update()

    @objc.python_method
    def distributionSmartCallback_(self, sender):
        Glyphs.defaults[DISTRIBUTION_KEY] = DISTRIBUTION_SMART
        self._set_distribution_ui(DISTRIBUTION_SMART)
        self.update()

    # -------------------------------------------------------------------
    # Preview callback
    # -------------------------------------------------------------------

    @objc.python_method
    def previewCallback_(self, sender):
        self.update()

    # -------------------------------------------------------------------
    # UI helpers
    # -------------------------------------------------------------------

    @objc.python_method
    def _set_tension_ui(self, value):
        self.paletteView.group.tensionSlider.set(value)
        self.paletteView.group.tensionField.set(self._format_value(value))

    @objc.python_method
    def _set_adjustment_ui(self, value):
        self.paletteView.group.adjustmentSlider.set(value)
        self.paletteView.group.adjustmentField.set(self._format_value(value))

    @objc.python_method
    def _set_distribution_ui(self, mode):
        self.paletteView.group.distributionBalanced.set(
            mode == DISTRIBUTION_BALANCED)
        self.paletteView.group.distributionPreserve.set(
            mode == DISTRIBUTION_PRESERVE)
        self.paletteView.group.distributionSmooth.set(
            mode == DISTRIBUTION_SMOOTH)
        self.paletteView.group.distributionSmart.set(
            mode == DISTRIBUTION_SMART)

    @objc.python_method
    def _format_value(self, value):
        """Format a 0–100 value for display. Show up to 1 decimal."""
        rounded = round(value, 1)
        if rounded == int(rounded):
            return str(int(rounded))
        return str(rounded)

    # -------------------------------------------------------------------
    # Core filter
    # -------------------------------------------------------------------

    @objc.python_method
    def filter(self, layer, inEditView, customParameters):
        # Preview bypass: when unchecked in the UI, skip all processing.
        # Only applies in the dialog (not as a custom parameter / filter).
        if not customParameters and inEditView:
            if not self.paletteView.group.previewCheckbox.get():
                return

        # Read parameters (all in 0–100 user-facing scale)
        if customParameters:
            tension_display = float(customParameters.get(
                "tension", DEFAULT_TENSION_DISPLAY))
            adjustment_display = float(customParameters.get(
                "adjustment", DEFAULT_ADJUSTMENT))
            distribution = str(customParameters.get(
                "distribution", DEFAULT_DISTRIBUTION))
        else:
            tension_display = float(Glyphs.defaults[TENSION_KEY])
            adjustment_display = float(Glyphs.defaults[ADJUSTMENT_KEY])
            distribution = str(Glyphs.defaults[DISTRIBUTION_KEY])

        selection = None
        if inEditView:
            selection = layer.selection

        for path in layer.paths:
            # --- Pass 1: Apply superellipticity to all curve segments ---
            # For preserve mode, save original handles before modification.
            # For smooth/smart mode, we need all segments processed before
            # the second pass, so we always complete this pass first.
            originals = {}  # index → (p1_orig_x, p1_orig_y, p2_orig_x, p2_orig_y)

            for i, node in enumerate(path.nodes):
                if node.type != CURVE:
                    continue

                # In edit view with selection: only process segments where
                # at least one node in the segment is selected
                if selection is not None and len(selection) > 0:
                    p0 = path.nodes[i - 3]
                    h1 = path.nodes[i - 2]
                    h2 = path.nodes[i - 1]
                    if (p0 not in selection and h1 not in selection
                            and h2 not in selection and node not in selection):
                        continue

                # Build the 4-point segment
                p0 = path.nodes[i - 3]
                p1 = path.nodes[i - 2]
                p2 = path.nodes[i - 1]
                p3 = node

                # Save original handle positions for preserve mode
                p1_orig_x = p1.position.x
                p1_orig_y = p1.position.y
                p2_orig_x = p2.position.x
                p2_orig_y = p2.position.y
                originals[i] = (p1_orig_x, p1_orig_y, p2_orig_x, p2_orig_y)

                # Step 1: Apply superellipticity (always balanced)
                result = compute_handles(
                    p0.position.x, p0.position.y,
                    p1_orig_x, p1_orig_y,
                    p2_orig_x, p2_orig_y,
                    p3.position.x, p3.position.y,
                    tension_display=tension_display,
                    adjustment_display=adjustment_display,
                )
                if result is None:
                    continue

                new_p1x, new_p1y, new_p2x, new_p2y = result

                # Step 2a: Redistribute toward original ratio (preserve mode)
                if distribution == DISTRIBUTION_PRESERVE:
                    new_p1x, new_p1y, new_p2x, new_p2y = redistribute_handles(
                        p0.position.x, p0.position.y,
                        p1_orig_x, p1_orig_y,
                        p2_orig_x, p2_orig_y,
                        new_p1x, new_p1y,
                        new_p2x, new_p2y,
                        p3.position.x, p3.position.y,
                    )

                p1.position = (new_p1x, new_p1y)
                p2.position = (new_p2x, new_p2y)

            # --- Pass 2 (Smooth only): Harmonize handles at smooth nodes ---
            if distribution == DISTRIBUTION_SMOOTH:
                n_nodes = len(path.nodes)
                for i, node in enumerate(path.nodes):
                    # Only process on-curve nodes with smooth connections
                    if node.type == OFFCURVE:
                        continue
                    if not node.smooth:
                        continue

                    # Check that both adjacent segments are curves:
                    # Previous node must be OFFCURVE (incoming handle)
                    # Next node must be OFFCURVE (outgoing handle)
                    prev_node = path.nodes[i - 1]
                    next_node = path.nodes[(i + 1) % n_nodes]
                    if prev_node.type != OFFCURVE:
                        continue
                    if next_node.type != OFFCURVE:
                        continue

                    # In edit view with selection: only harmonize nodes
                    # where at least one adjacent handle or the node itself
                    # is selected
                    if selection is not None and len(selection) > 0:
                        a2 = path.nodes[i - 1]
                        b1 = path.nodes[(i + 1) % n_nodes]
                        if (node not in selection
                                and a2 not in selection
                                and b1 not in selection):
                            continue

                    # Segment A: p0a → a1 → a2 → node
                    p0a = path.nodes[i - 3]
                    a1 = path.nodes[i - 2]
                    a2 = path.nodes[i - 1]

                    # Segment B: node → b1 → b2 → p3b
                    b1 = path.nodes[(i + 1) % n_nodes]
                    b2 = path.nodes[(i + 2) % n_nodes]
                    p3b = path.nodes[(i + 3) % n_nodes]

                    result = smooth_handles_at_node(
                        p0a.position.x, p0a.position.y,
                        a1.position.x, a1.position.y,
                        a2.position.x, a2.position.y,
                        node.position.x, node.position.y,
                        b1.position.x, b1.position.y,
                        b2.position.x, b2.position.y,
                        p3b.position.x, p3b.position.y,
                    )

                    new_a2x, new_a2y, new_b1x, new_b1y = result
                    a2.position = (new_a2x, new_a2y)
                    b1.position = (new_b1x, new_b1y)

            # --- Pass 2 (Smart only): Move on-curve nodes for G2 ---
            if distribution == DISTRIBUTION_SMART:
                n_nodes = len(path.nodes)
                for i, node in enumerate(path.nodes):
                    if node.type == OFFCURVE:
                        continue
                    if not node.smooth:
                        continue

                    prev_node = path.nodes[i - 1]
                    next_node = path.nodes[(i + 1) % n_nodes]
                    if prev_node.type != OFFCURVE:
                        continue
                    if next_node.type != OFFCURVE:
                        continue

                    if selection is not None and len(selection) > 0:
                        a2 = path.nodes[i - 1]
                        b1 = path.nodes[(i + 1) % n_nodes]
                        if (node not in selection
                                and a2 not in selection
                                and b1 not in selection):
                            continue

                    # Segment A: p0a → a1 → a2 → node
                    p0a = path.nodes[i - 3]
                    a1 = path.nodes[i - 2]
                    a2 = path.nodes[i - 1]

                    # Segment B: node → b1 → b2 → p3b
                    b1 = path.nodes[(i + 1) % n_nodes]
                    b2 = path.nodes[(i + 2) % n_nodes]
                    p3b = path.nodes[(i + 3) % n_nodes]

                    new_nx, new_ny = smart_node_position(
                        p0a.position.x, p0a.position.y,
                        a1.position.x, a1.position.y,
                        a2.position.x, a2.position.y,
                        node.position.x, node.position.y,
                        b1.position.x, b1.position.y,
                        b2.position.x, b2.position.y,
                        p3b.position.x, p3b.position.y,
                    )

                    node.position = (new_nx, new_ny)

    # -------------------------------------------------------------------
    # Custom parameter for export
    # -------------------------------------------------------------------

    @objc.python_method
    def generateCustomParameter(self):
        distribution = str(Glyphs.defaults[DISTRIBUTION_KEY])
        parts = "%s; tension:%s; adjustment:%s" % (
            self.__class__.__name__,
            self._format_value(float(Glyphs.defaults[TENSION_KEY])),
            self._format_value(float(Glyphs.defaults[ADJUSTMENT_KEY])),
        )
        if distribution != DEFAULT_DISTRIBUTION:
            parts += "; distribution:%s" % distribution
        return parts

    @objc.python_method
    def __file__(self):
        return __file__
