"""cadkit — code-CAD toolkit for build123d.

Units are mm throughout. Four namespaces:

- ``cadkit.core``  — ``Design``, the export runner, probe and summary output
- ``cadkit.draw``  — HLR projection to SVG: shop drawings, exploded views, ``iso()``
- ``cadkit.wood``  — woodworking: joinery, cut lists, sheet nesting, cut plans
- ``cadkit.print`` — FDM: printability checks, bed fit, optional slicer stage

``cadkit.verify`` holds the golden-PNG visual diff behind the ``cadkit``
console script.
"""

__version__ = "0.1.0"
