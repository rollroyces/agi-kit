"""IRT calibration package for the ARC-AGI enhancement project.

Modules:
    irt_model       -- 2PL/3PL model, likelihood, joint MAP fitting
    data_generator  -- synthetic ARC-like response matrix simulator
    fitter          -- high-level fit/inspect helpers
    visualization   -- ICC curves, ability histogram, accuracy-vs-theta
"""

from . import irt_model, data_generator, fitter, visualization  # noqa: F401