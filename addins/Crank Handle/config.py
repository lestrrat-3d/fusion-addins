from __future__ import annotations

import os

# Autodesk template flag read by addinkit.general_utils (console logging).
DEBUG = False

# Full commit ID of decad-gallery that this add-in was generated from. Set by the generator on every regeneration.
GALLERY_REVISION = "77eca2ef5bc3a08038d0626e7eaa8546fbf5678f"

ADDIN_NAME = os.path.basename(os.path.dirname(__file__))
COMPANY_NAME = "lestrrat3d"
CMD_ID = f"{COMPANY_NAME}_crankhandle_create"
CMD_NAME = "Crank Handle"
CMD_DESCRIPTION = "Builds the decad-gallery crank handle."
WORKSPACE_ID = "FusionSolidEnvironment"
PANEL_ID = "SolidCreatePanel"
# Empty: the button goes at the end of the Create panel.
COMMAND_BESIDE_ID = ""
