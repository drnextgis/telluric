import warnings
import numpy as np

from affine import Affine, TransformNotInvertibleError
from rasterio import features
from rasterio.dtypes import get_minimum_dtype
from rasterio._err import CPLE_OutOfMemoryError  # noqa

from telluric.georaster import GeoRaster2


NODATA_VALUE = 0
# FILL_VALUE = np.iinfo(np.uint8).max
FILL_VALUE = 1

NODATA_DEPRECATION_WARNING = ("Passing nodata_value to rasterize is not supported anymore. "
                              "An appropriate nodata value will be generated, depending on the fill value(s).")


class ScaleError(ValueError):
    pass


def rasterize(shapes, crs, bounds=None, dest_resolution=None, *, fill_value=None,
              band_names=None, dtype=None, shape=None, ul_corner=None, **kwargs):
    if fill_value is None:
        fill_value = FILL_VALUE

    # If no dtype is given, we select it depending on the fill value
    if dtype is None:
        dtype = get_minimum_dtype(fill_value)

    nodata_value = kwargs.get('nodata_value', NODATA_VALUE)
    if nodata_value is not None:
        warnings.warn(NODATA_DEPRECATION_WARNING, DeprecationWarning)

    if not(dest_resolution):
        raise ValueError("dest_resolution must be specified")

    # We do not want to use a nodata value that the user is explicitly filling,
    # so in this case we use an alternative value
    if fill_value == nodata_value:
        if np.issubdtype(dtype, np.integer):
            nodata_value = np.iinfo(dtype).max - nodata_value
        else:
            nodata_value = np.finfo(dtype).max - nodata_value

    if band_names is None:
        band_names = [1]

    if bounds:
        # Affine transformation
        minx, miny, maxx, maxy = bounds.bounds

        # Compute size from scale
        dx = maxx - minx
        dy = maxy - miny
        sx = round(dx / dest_resolution)
        sy = round(dy / dest_resolution)
    elif shape and ul_corner:
        minx, maxy = ul_corner
        sx, sy = shape
    else:
        raise ValueError("Either bounds or shape + ul_corner must be specified")

    affine = Affine.translation(minx, maxy) * Affine.scale(dest_resolution, -dest_resolution)
    sz = len(band_names)

    if sx == 0 or sy == 0:
        raise ScaleError("Scale is too coarse, decrease it for a bigger image")

    try:
        if not shapes:
            image = np.full((sz, sy, sx), nodata_value, dtype=dtype)

        else:
            image = features.rasterize(
                shapes,
                out_shape=(sy, sx), fill=nodata_value, transform=affine, default_value=fill_value)

    except TransformNotInvertibleError:
        raise ScaleError("Scale is too coarse, decrease it for a bigger image")

    except (MemoryError, ValueError, CPLE_OutOfMemoryError):
        raise ScaleError("Scale is too fine, increase it for a smaller image")

    else:
        return GeoRaster2(image, affine, crs, nodata=nodata_value, band_names=band_names)
