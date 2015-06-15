from spillway.compat import mapnik

def add_colorizer_stops(style, bins, mcolors):
    rule = style.rules[0]
    symbolizer = rule.symbols[0]
    for value, color in zip(bins, mcolors):
        symbolizer.colorizer.add_stop(value, mapnik.Color(color))
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
