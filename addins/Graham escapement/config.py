from __future__ import annotations

import os

# Autodesk template flag read by addinkit.general_utils (console logging).
DEBUG = False

# Full commit ID of decad-gallery that this add-in was generated from. Set by the generator on every regeneration.
GALLERY_REVISION = "3a4f9d8dc3d5ea6ed7ca003efec7be0467525492"

ADDIN_NAME = os.path.basename(os.path.dirname(__file__))
COMPANY_NAME = "lestrrat3d"
CMD_ID = f"{COMPANY_NAME}_escapement_create"
CMD_NAME = "Graham Escapement"
CMD_DESCRIPTION = "Builds the decad-gallery Graham escapement."
WORKSPACE_ID = "FusionSolidEnvironment"
PANEL_ID = "SolidCreatePanel"
# Empty: the button goes at the end of the Create panel.
COMMAND_BESIDE_ID = ""
