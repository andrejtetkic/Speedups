#!/usr/bin/python3
# copyright (c) 2018- polygoniq xyz s.r.o.

import bpy
import typing
import os

ICON_DIR_NAME = "icons"


class SocialMediaURL:
    DISCORD = "https://www.polygoniq.com/discord"
    FACEBOOK = "https://www.facebook.com/polygoniq/"
    INSTAGRAM = "https://www.instagram.com/polygoniq.xyz/"
    BLENDERMARKET = "https://blendermarket.com/creators/polygoniq"
    WEBPAGE = "https://polygoniq.com/"
    GUMROAD = "https://gumroad.com/polygoniq"


class IconManager:
    def __init__(self, additional_paths: typing.Optional[typing.List[str]] = None):
        self.icon_previews = bpy.utils.previews.new()
        self.additional_paths = additional_paths if additional_paths is not None else []
        self.load_all()

    def load_all(self) -> None:
        icons_dir = os.path.join(os.path.dirname(__file__), ICON_DIR_NAME)
        self.load_icons_from_directory(icons_dir)

        for path in self.additional_paths:
            self.load_icons_from_directory(os.path.join(path, ICON_DIR_NAME))

    def load_icons_from_directory(self, path: str) -> None:
        if not os.path.isdir(path):
            raise RuntimeError(f"Cannot load icons from {path}, it is not valid dir")

        for icon_filename in os.listdir(path):
            self.load_icon(icon_filename, path)

    def load_icon(self, filename: str, path: str) -> None:
        if not filename.endswith((".jpg", ".png")):
            return

        icon_basename, _ = os.path.splitext(filename)
        if icon_basename in self.icon_previews:
            return

        self.icon_previews.load(icon_basename, os.path.join(
            path, filename), "IMAGE")

    def get_icon(self, icon_name: str) -> bpy.types.ImagePreview:
        return self.icon_previews[icon_name]

    def get_icon_id(self, icon_name: str) -> int:
        return self.icon_previews[icon_name].icon_id

    def get_polygoniq_addon_icon_id(self, addon_name: str) -> int:
        icon_name = f"logo_{addon_name}"
        if icon_name in self.icon_previews:
            return self.icon_previews[icon_name].icon_id
        else:
            return 1  # questionmark icon_id

    def draw_logo(self, layout: bpy.types.UILayout, show_text: bool = False):
        label_text = "© polygoniq xyz s.r.o" if show_text else ""
        layout.label(text=label_text, icon_value=self.get_icon_id("logo_polygoniq"))


icon_manager = IconManager()


def draw_settings_footer(layout: bpy.types.UILayout):
    row = layout.row(align=True)
    row.alignment = "CENTER"
    row.scale_x = 1.27
    row.scale_y = 1.27
    draw_social_media_buttons(row, show_text=False)
    row.label(text="© polygoniq xyz s.r.o")


def draw_social_media_buttons(layout: bpy.types.UILayout, show_text: bool = False):
    layout.operator("wm.url_open",
                    text="Discord" if show_text else "",
                    icon_value=icon_manager.get_icon_id("logo_discord")
                    ).url = SocialMediaURL.DISCORD

    layout.operator("wm.url_open",
                    text="Facebook" if show_text else "",
                    icon_value=icon_manager.get_icon_id("logo_facebook")
                    ).url = SocialMediaURL.FACEBOOK

    layout.operator("wm.url_open",
                    text="Instagram" if show_text else "",
                    icon_value=icon_manager.get_icon_id("logo_instagram")
                    ).url = SocialMediaURL.INSTAGRAM

    layout.operator("wm.url_open",
                    text="BlenderMarket" if show_text else "",
                    icon_value=icon_manager.get_icon_id("logo_blendermarket")
                    ).url = SocialMediaURL.BLENDERMARKET

    layout.operator("wm.url_open",
                    text="Gumroad" if show_text else "",
                    icon_value=icon_manager.get_icon_id("logo_gumroad")
                    ).url = SocialMediaURL.GUMROAD

    layout.operator("wm.url_open",
                    text="Website" if show_text else "",
                    icon_value=icon_manager.get_icon_id("logo_polygoniq")
                    ).url = SocialMediaURL.WEBPAGE


def show_message_box(message: str, title: str, icon: str = 'INFO') -> None:
    lines = message.split("\n")

    def draw(self, context):
        for line in lines:
            row = self.layout.row()
            row.label(text=line)

    bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)


def multi_column(
    layout: bpy.types.UILayout,
    column_sizes: typing.List[float],
    align: bool = False
) -> typing.List[bpy.types.UILayout]:
    columns = []
    for i in range(len(column_sizes)):
        # save first column, create split from the other with recalculated size
        size = 1.0 - sum(column_sizes[:i]) if i > 0 else 1.0

        s = layout.split(factor=column_sizes[i] / size, align=align)
        a = s.column(align=align)
        b = s.column(align=align)
        columns.append(a)
        layout = b

    return columns


def scaled_row(
    layout: bpy.types.UILayout,
    scale: float,
    align: bool = False
) -> bpy.types.UILayout:
    row = layout.row(align=align)
    row.scale_x = row.scale_y = scale
    return row
