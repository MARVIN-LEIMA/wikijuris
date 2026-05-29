from .cad_primitives import register as register_cad
from .surfaces import register as register_surfaces
from .parcels import register as register_parcels
from .pipes import register as register_pipes
from .roads import register as register_roads

__all__ = [
    "register_cad",
    "register_surfaces",
    "register_parcels",
    "register_pipes",
    "register_roads",
]
