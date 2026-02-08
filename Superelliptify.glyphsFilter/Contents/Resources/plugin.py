# -*- coding: utf-8 -*-
"""
Superelliptify — A Glyphs 3 Filter Plugin

Adjusts cubic Bézier curve handle lengths along the diamond → circle → squircle
spectrum, with eccentricity-aware adjustment for oblong shapes.
"""

import objc
import os
import sys

from GlyphsApp import Glyphs, CURVE
from GlyphsApp.plugins import FilterWithDialog
from vanilla import Group, Slider, TextBox, EditText, SquareButton, Window

# Import core algorithm from sibling module
plugin_dir = os.path.dirname(__file__)
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)
from SuperelliptifyCore import (
    compute_handles,
    PRESET_CIRCLE,
    PRESET_OPTICAL,
    PRESET_TYPE,
    PRESET_SQUIRCLE,
    DEFAULT_TENSION_DISPLAY,
    DEFAULT_ADJUSTMENT,
)

# Glyphs.defaults keys
TENSION_KEY = "com.superelliptify.tension"
ADJUSTMENT_KEY = "com.superelliptify.adjustment"


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
        width = 270
        height = 90

        self.paletteView = Window((width, height))
        self.paletteView.group = Group((0, 0, width, height))

        # --- Preset buttons row ---
        y = 8
        buttonW = 46
        gap = 3
        x = 10
        self.paletteView.group.presetLabel = TextBox(
            (x, y + 1, 52, 17),
            "Tension:",
            sizeStyle="small",
        )
        x = 66
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

        # --- Tension slider row ---
        y = 33
        self.paletteView.group.tensionSlider = Slider(
            (66, y, -58, 17),
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
            (10, y + 1, 52, 17),
            "Adjust:",
            sizeStyle="small",
        )
        self.paletteView.group.adjustmentSlider = Slider(
            (66, y, -58, 17),
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

        # Expose vanilla view as the Glyphs dialog
        self.dialog = self.paletteView.group.getNSView()

    @objc.python_method
    def start(self):
        Glyphs.registerDefault(TENSION_KEY, DEFAULT_TENSION_DISPLAY)
        Glyphs.registerDefault(ADJUSTMENT_KEY, DEFAULT_ADJUSTMENT)
        # Restore saved values to UI
        tension = float(Glyphs.defaults[TENSION_KEY])
        adjustment = float(Glyphs.defaults[ADJUSTMENT_KEY])
        self._set_tension_ui(tension)
        self._set_adjustment_ui(adjustment)

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
        # Read parameters (all in 0–100 user-facing scale)
        if customParameters:
            tension_display = float(customParameters.get(
                "tension", DEFAULT_TENSION_DISPLAY))
            adjustment_display = float(customParameters.get(
                "adjustment", DEFAULT_ADJUSTMENT))
        else:
            tension_display = float(Glyphs.defaults[TENSION_KEY])
            adjustment_display = float(Glyphs.defaults[ADJUSTMENT_KEY])

        selection = None
        if inEditView:
            selection = layer.selection

        for path in layer.paths:
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

                result = compute_handles(
                    p0.position.x, p0.position.y,
                    p1.position.x, p1.position.y,
                    p2.position.x, p2.position.y,
                    p3.position.x, p3.position.y,
                    tension_display=tension_display,
                    adjustment_display=adjustment_display,
                )
                if result is None:
                    continue

                new_p1x, new_p1y, new_p2x, new_p2y = result
                p1.position = (new_p1x, new_p1y)
                p2.position = (new_p2x, new_p2y)

    # -------------------------------------------------------------------
    # Custom parameter for export
    # -------------------------------------------------------------------

    @objc.python_method
    def generateCustomParameter(self):
        return "%s; tension:%s; adjustment:%s" % (
            self.__class__.__name__,
            self._format_value(float(Glyphs.defaults[TENSION_KEY])),
            self._format_value(float(Glyphs.defaults[ADJUSTMENT_KEY])),
        )

    @objc.python_method
    def __file__(self):
        return __file__
