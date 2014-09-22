import mapnik
import numpy as np

colors = {'YlGnBu': ('#edf8b1', '#7fcdbb', '#2c7fb8'),
          'bluered': ('blue', 'red')}

def add_colorizer_stops(style, values, name=None):
    ramp = colors.get(name or 'YlGnBu')
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
