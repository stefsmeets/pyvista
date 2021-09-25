"""These are private methods we keep out of plotting.py to simplfy the module."""
import warnings

import numpy as np
import pyvista

from pyvista.utilities import get_array, is_pyvista_dataset
from .tools import opacity_transfer_function


def _has_matplotlib():
    try:
        import matplotlib
        return True
    except ImportError:  # pragma: no cover
        return False


def prepare_smooth_shading(mesh, scalars, texture, split_sharp_edges, feature_angle):
    """Prepare a dataset for smooth shading.

    VTK requires datasets with prong shading to have active normals.
    This requires extracting the external surfaces from non-polydata
    datasets and computing the point normals.

    Parameters
    ----------
    mesh : pyvista.DataSet
        Dataset to prepare smooth shading for.
    texture : vtk.vtkTexture or np.ndarray or bool, optional
        A texture to apply to the mesh.
    split_sharp_edges : bool, optional
        Split sharp edges exceeding 30 degrees when plotting with
        smooth shading.  Control the angle with the optional
        keyword argument ``feature_angle``.  By default this is
        ``False``.  Note that enabling this will create a copy of
        the input mesh within the plotter.  See
        :ref:`shading_example`.
    feature_angle : float, optional
        Angle to consider an edge a sharp edge.

    Returns
    -------
    pyvista.PolyData
        Always a surface as we need to compute point normals.

    """
    is_polydata = isinstance(mesh, pyvista.PolyData)
    indices_array = None

    # extract surface if not already a surface
    if not is_polydata:
        mesh = mesh.extract_surface()
        indices_array = 'vtkOriginalPointIds'

    if texture:
        tcoords = mesh.active_t_coords

    if split_sharp_edges:
        if is_polydata:
            # we must track the original IDs with our own array
            indices_array = '__orig_ids__'
            mesh.point_data[indices_array] = np.arange(mesh.n_points, dtype=np.int32)
        mesh = mesh.compute_normals(
            cell_normals=False,
            split_vertices=True,
            feature_angle=feature_angle,
        )
    else:
        # if mesh.point_data.active_normals is None:
        mesh.compute_normals(cell_normals=False, inplace=True)

    if scalars is not None and indices_array is not None:
        ind = mesh.point_data[indices_array]
        scalars = np.asarray(scalars)[ind]

    if texture:
        if indices_array is not None:
            ind = mesh.point_data[indices_array]
            tcoords = tcoords[ind]
        mesh.active_t_coords = tcoords

    # remove temporary indices array
    if indices_array == '__orig_ids__':
        del mesh.point_data['__orig_ids__']

    return mesh, scalars


def process_opacity(mesh, opacity, preference, n_colors, scalars, use_transparency):
    """Process opacity.

    This function accepts an opacity string or array and always
    returns an array that can be applied to a dataset for plotting.

    Parameters
    ----------
    mesh : pyvista.DataSet
        Dataset to process the opacity for.
    opacity : str, numpy.ndarray
        String or array.  If string, must be a cell or point data array.
        preference : str, optional
            When ``mesh.n_points == mesh.n_cells``, this parameter
            sets how the scalars will be mapped to the mesh.  Default
            ``'points'``, causes the scalars will be associated with
            the mesh points.  Can be either ``'points'`` or
            ``'cells'``.
    n_colors : int, optional
        Number of colors to use when displaying the opacity.
    scalars : numpy.ndarray, optional
        Dataset scalars.
    use_transparency : bool, optional
        Invert the opacity mappings and make the values correspond
        to transparency.

    Returns
    -------
    _custom_opac : bool
        If using custom opacity.
    opacity : numpy.ndarray
        Array containing the opacity.

    """
    _custom_opac = False
    if isinstance(opacity, str):
        try:
            # Get array from mesh
            opacity = get_array(mesh, opacity,
                                preference=preference, err=True)
            if np.any(opacity > 1):
                warnings.warn("Opacity scalars contain values over 1")
            if np.any(opacity < 0):
                warnings.warn("Opacity scalars contain values less than 0")
            _custom_opac = True
        except:
            # Or get opacity transfer function
            opacity = opacity_transfer_function(opacity, n_colors)
        else:
            if scalars.shape[0] != opacity.shape[0]:
                raise ValueError(
                    "Opacity array and scalars array must have the same number "
                    "of elements."
                )
    elif isinstance(opacity, (np.ndarray, list, tuple)):
        opacity = np.array(opacity)
        if opacity.shape[0] in [mesh.n_cells, mesh.n_points]:
            # User could pass an array of opacities for every point/cell
            _custom_opac = True
        else:
            opacity = opacity_transfer_function(opacity, n_colors)

    if use_transparency and np.max(opacity) <= 1.0:
        opacity = 1 - opacity
    elif use_transparency and isinstance(opacity, np.ndarray):
        opacity = 255 - opacity

    return _custom_opac, opacity