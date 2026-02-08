# Superelliptify

A filter plugin for [Glyphs 3](https://glyphsapp.com) that adjusts cubic Bézier curve handles along the circle–squircle approximation spectrum using the Tension parameter.

The optional Adjustment parameter allows for adaptive curve Tension application that follows segment geometry. It increases Tension for more oblong shapes, reflecting a pattern found across many typefaces and font families.

The algorithm scales its effect to the turning angle of each segment. Shorter curve segments receive proportionally less change, preserving shapes defined by deliberately placed on-curve points. This allows for non-destructive application to multiple shapes at once (e.g. for prototyping).

<img src="images/superelliptify.png" width="700" height="620" alt="Superelliptify plugin in Glyphs 3 app">

Based on a custom algorithm designed in 2015 by Maciej Ratajski.

## What it does

Superelliptify controls how "round" or "square" your curves are by adjusting off-curve handle lengths. It works across the range from circle (~55% for a 90° arc) to squircle (100% handles for a 90° arc).

Two parameters:

- **Tension** (0–100) — controls the superellipticity. 0 = exact circle approximation, 13 = optically correct circle, 20 = a good default for type design, 100 = full squircle.
- **Adjustment** (0–100) — eccentricity compensation. At higher values, more oblong shapes are pushed further toward squircle-like forms. This reflects a pattern observed across many typefaces: narrow shapes tend to resemble rounded rectangles rather than squished circles.

Preset buttons for quick access: **Circle · Optical · Type · Squircle**

A specific balance of the two parameters can be apllied among multiple glyphs of the same font family.

<img src="images/recta.png" width="370" height="530" alt="Nebite Torino Recta Typeface">

## Key properties of the algorithm

- Uses the Bézier circle approximation as its mathematical baseline, generalized to any segment angle
- Preserves shapes with user-placed on-curve points — segments with small turning angles receive minimal adjustment
- Eccentricity-aware: the Adjustment parameter makes oblong shapes trend toward rounded-rectangle forms, matching the stylistic consistency found in many real typefaces
- Works on selected segments, whole glyphs, or across multiple glyphs, whole fonts, and font familes
- Can be used as a Custom Parameter on export for quick prototyping

## Installation

Double-click `Superelliptify.glyphsFilter` to install, or copy it to:

```
~/Library/Application Support/Glyphs 3/Plugins/
```

Restart Glyphs after installing.

## Usage

**Filter menu** → **Superelliptify**

Select curve segments (or select all), adjust the sliders, and click Apply.

**As a Custom Parameter** (for export instances):

```
Superelliptify; tension:20; adjustment:50
```

## Algorithm

Algorithm designed in 2015 by Maciej Ratajski.

Plugin structure informed by the [Curve Equalizer](https://github.com/jenskutilek/Curve-Equalizer) by Jens Kutilek.

## License

MIT
