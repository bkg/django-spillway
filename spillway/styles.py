import mapnik
import numpy as np

def gradient(colors=((0, 'blue'), (255, 'red'))):
    """Returns a basic linear gradient as a RasterColorizer."""
    colorizer = mapnik.RasterColorizer(mapnik.COLORIZER_LINEAR,
                                       mapnik.Color(0, 0, 0, 255))
    for color in colors:
        colorizer.add_stop(color[0], mapnik.Color(color[1]))
    return colorizer

def get_raster_style(needs_gradient=True):
    """Returns a default raster Style."""
    style = mapnik.Style()
    rule = mapnik.Rule()
    symbolizer = mapnik.RasterSymbolizer()
    if needs_gradient:
        symbolizer.colorizer = gradient()
    rule.symbols.append(symbolizer)
    style.rules.append(rule)
    return style

def adjust_to_minmax(colorizer, extrema):
    """Adjust RasterColorizer to equal intervals."""
    # Generate equal interval bins from min/max pixel values.
    breaks = np.linspace(*extrema + (len(colorizer.stops),))
    # Update the stop values for the color ramp.
    for stop, breakval in zip(colorizer.stops, breaks):
        stop.value = breakval
    return colorizer
