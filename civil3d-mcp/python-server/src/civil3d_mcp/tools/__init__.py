from .cad_primitives import register as register_cad
from .surfaces import register as register_surfaces
from .parcels import register as register_parcels
from .pipes import register as register_pipes
from .roads import register as register_roads
from .points import register as register_points
from .scripts import register as register_scripts
from .drawing import register as register_drawing

__all__ = [
    "register_cad",
    "register_surfaces",
    "register_parcels",
    "register_pipes",
    "register_roads",
    "register_points",
    "register_scripts",
    "register_drawing",
]
