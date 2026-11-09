from __future__ import annotations

import os

# Autodesk template flag read by addinkit.general_utils (console logging).
DEBUG = False

# Full commit ID of decad-gallery that this add-in was generated from. Set by the generator on every regeneration.
GALLERY_REVISION = "4a452cdc74e783b7e8eb5512cec68d196423dbe4"

ADDIN_NAME = os.path.basename(os.path.dirname(__file__))
COMPANY_NAME = "lestrrat3d"
CMD_ID = f"{COMPANY_NAME}_planetarygearbox_create"
CMD_NAME = "Planetary Gearbox"
CMD_DESCRIPTION = "Builds the decad-gallery planetary gearbox."
WORKSPACE_ID = "FusionSolidEnvironment"
PANEL_ID = "SolidCreatePanel"
# Empty: the button goes at the end of the Create panel.
COMMAND_BESIDE_ID = ""
