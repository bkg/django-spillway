import mapnik
import numpy as np

# ColorBrewer http://colorbrewer2.org/
colors = {'YlGnBu': ('#ffffd9', '#edf8b1', '#c7e9b4', '#7fcdbb', '#41b6c4',
                     '#1d91c0', '#225ea8', '#253494', '#081d58'),

          'YlOrRd': ('#ffffcc', '#ffeda0', '#fed976', '#feb24c', '#fd8d3c',
                     '#fc4e2a', '#e31a1c', '#bd0026', '#800026')}

def add_colorizer_stops(style, values, name=None):
    ramp = colors.get(name) or colors['YlGnBu']
    if not ramp:
        raise ValueError('No color ramp found for "%s"' % name)
    breaks = np.linspace(values[0], values[-1], len(ramp))
    rule = style.rules[0]
    symbolizer = rule.symbols[0]
    for value, color in zip(breaks, ramp):
        symbolizer.colorizer.add_stop(value, mapnik.Color(color))
    return style

def find_or_append(stylename, canvas):
    try:
        style = canvas.find_style(stylename)
    except KeyError:
        style = make_raster_style()
        canvas.append_style(stylename, style)
    return style

def make_raster_style():
    """Returns a default raster Style."""
    style = mapnik.Style()
    rule = mapnik.Rule()
    symbolizer = mapnik.RasterSymbolizer()
    symbolizer.colorizer = mapnik.RasterColorizer(
        mapnik.COLORIZER_LINEAR, mapnik.Color(0, 0, 0, 255))
    rule.symbols.append(symbolizer)
    style.rules.append(rule)
    return style
