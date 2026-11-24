from __future__ import annotations

import os

# Autodesk template flag read by addinkit.general_utils (console logging).
DEBUG = False

# Full commit ID of decad-gallery that this add-in was generated from. Set by the generator on every regeneration.
GALLERY_REVISION = "cbbb2ca062d31dfe662fe7963f8a7c536b89a7b2"

# Build the large parts in a design of their own and import them (commands/sevensegment/isolate.py), which keeps the
# main design's timeline short. Opening and closing documents inside a command's execute handler left its undo step
# unusable, and the import then failed with `InternalValidationError : pBase` (knowledge/performance.md). So execute
# only fires a custom event. The event handler makes the archives outside any command, then starts a command of its own
# that builds in the main design: Undo takes the whole build back in one step.
ISOLATE_PARTS = True
BUILD_AFTER_COMMAND = True

ADDIN_NAME = os.path.basename(os.path.dirname(__file__))
COMPANY_NAME = "lestrrat3d"
CMD_ID = f"{COMPANY_NAME}_sevensegment_create"
CMD_NAME = "Seven-segment display"
CMD_DESCRIPTION = "Builds the decad-gallery seven-segment display."
WORKSPACE_ID = "FusionSolidEnvironment"
PANEL_ID = "SolidCreatePanel"
# Empty: the button goes at the end of the Create panel.
COMMAND_BESIDE_ID = ""
