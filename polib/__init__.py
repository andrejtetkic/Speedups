#!/usr/bin/python3
# copyright (c) 2018- polygoniq xyz s.r.o.

import bpy

if "asset_addon" not in locals():
    from . import asset_addon
    from . import linalg
    from . import telemetry_module as telemetry_native_module
    from . import utils
    from . import ui
    from . import snap_to_ground

else:
    import importlib
    asset_addon = importlib.reload(asset_addon)
    linalg = importlib.reload(linalg)
    telemetry_native_module = importlib.reload(telemetry_native_module)
    utils = importlib.reload(utils)
    ui = importlib.reload(ui)
    snap_to_ground = importlib.reload(snap_to_ground)


# fake bl_info so that this gets picked up by vscode blender integration
bl_info = {
    "name": "polib",
    "description": "",
}


def init_polygoniq_global():
    global telemetry_module

    if not hasattr(bpy, "polygoniq_global"):
        bpy.polygoniq_global = {
            "telemetry": {},  # deprecated!
            "telemetry_module": {}
        }

    if not hasattr(bpy.polygoniq_global, "telemetry_module"):
        bpy.polygoniq_global["telemetry_module"] = {}

    # another polygoniq addon might have already initialized telemetry!
    # we want to use just one instance unless it's a different API version
    if telemetry_native_module.API_VERSION in bpy.polygoniq_global["telemetry_module"]:
        telemetry_module = bpy.polygoniq_global["telemetry_module"][telemetry_native_module.API_VERSION]
    else:
        telemetry_module = telemetry_native_module
        bpy.polygoniq_global["telemetry_module"][telemetry_native_module.API_VERSION] = telemetry_module
        telemetry_module.bootstrap_telemetry()


init_polygoniq_global()


def get_telemetry(product: str):
    return telemetry_module.get_telemetry(product)


__all__ = ["asset_addon", "get_telemetry", "linalg", "utils", "ui", "snap_to_ground"]
