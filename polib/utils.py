#!/usr/bin/python3
# copyright (c) 2018- polygoniq xyz s.r.o.

import bpy
import bpy.utils.previews
import sys
import shutil
import os
import typing
import datetime
import functools
import subprocess
import time
import re
import uuid


def autodetect_install_path(product: str, init_path: str, install_path_checker: typing.Callable[[str], bool]) -> str:
    big_zip_path = os.path.abspath(os.path.dirname(init_path))
    if install_path_checker(big_zip_path):
        print(f"{product} install dir autodetected as {big_zip_path} (big zip embedded)")
        return big_zip_path

    if sys.platform == "win32":
        SHOTS_IN_THE_DARK = [
            f"C:/{product}",
            f"D:/{product}",
            f"C:/polygoniq/{product}",
            f"D:/polygoniq/{product}",
        ]

        for shot in SHOTS_IN_THE_DARK:
            if install_path_checker(shot):
                print(f"{product} install dir autodetected as {shot}")
                return os.path.abspath(shot)

    elif sys.platform in ["linux", "darwin"]:
        SHOTS_IN_THE_DARK = [
            os.path.expanduser(f"~/{product}"),
            os.path.expanduser(f"~/Desktop/{product}"),
            os.path.expanduser(f"~/Documents/{product}"),
            os.path.expanduser(f"~/Downloads/{product}"),
            os.path.expanduser(f"~/polygoniq/{product}"),
            os.path.expanduser(f"~/Desktop/polygoniq/{product}"),
            os.path.expanduser(f"~/Documents/polygoniq/{product}"),
            os.path.expanduser(f"~/Downloads/polygoniq/{product}"),
            f"/var/lib/{product}",
            f"/usr/local/{product}",
            f"/opt/{product}",
        ]

        for shot in SHOTS_IN_THE_DARK:
            if install_path_checker(shot):
                print(f"{product} install dir autodetected as {shot}")
                return os.path.abspath(shot)

    print(
        f"{product} is not installed in one of the default locations, please make "
        f"sure the path is set in {product} addon preferences!", file=sys.stderr)
    return ""


def absolutize_install_path(self, context):
    if hasattr(self, "botaniq_path"):
        abs_ = os.path.abspath(self.botaniq_path)
        if abs_ != self.botaniq_path:
            self.botaniq_path = abs_
    if hasattr(self, "materialiq_path"):
        abs_ = os.path.abspath(self.materialiq_path)
        if abs_ != self.materialiq_path:
            self.materialiq_path = abs_
    if hasattr(self, "move_installation_destination_path"):
        abs_ = os.path.abspath(self.move_installation_destination_path)
        if abs_ != self.move_installation_destination_path:
            self.move_installation_destination_path = abs_
    return None


def move_installation(product: str, old_path: str, new_path: str, install_dir_checker: typing.Callable[[str], bool]) -> str:
    if os.path.islink(old_path):
        print(f"Path ({old_path}) is a symlink\nMoving it may break the symlinks!", file=sys.stderr)
        return ""

    if os.path.isfile(new_path):
        print(
            f"Cannot move installation, provided new path {new_path} points "
            f"to a file.", file=sys.stderr)
        return ""

    if not install_dir_checker(old_path):
        print(
            f"Cannot move installation, provided old path {old_path} is not a valid "
            f"{product} install directory.", file=sys.stderr)
        return ""

    if os.path.abspath(bpy.path.abspath(old_path)) == os.path.abspath(bpy.path.abspath(new_path)):
        print(
            f"Old path {old_path} and new path {new_path} point to the same directory. "
            f"Cancelling!", file=sys.stderr)
        return ""

    if install_dir_checker(new_path):
        # Destination dir is a valid installation. In this case we avoid the copy.
        # This is a common use-case where people have multiple blender versions and re-use
        # the same materialiq or botaniq.
        print(
            f"Destination directory {new_path} already contains a {product} installation!"
            f"Skipping the copy.", file=sys.stderr)
    else:
        if os.path.isdir(new_path):
            # sometimes people choose C:/Documents or such, in this case we create a new folder
            new_path = os.path.join(new_path, product)

        # we copy everything (inc. the python files) so we can track the installation version aferwards
        print(f"Copying {old_path} to {new_path}", file=sys.stderr)
        shutil.copytree(old_path, new_path)

    if not install_dir_checker(new_path):
        print(
            f"Something failed while copying! {new_path} is not a valid {product} installation!",
            file=sys.stderr)
        return ""

    for f in os.listdir(old_path):
        full_path = os.path.join(old_path, f)

        # do not remove python files from the previous installation if it is the blender addons path
        addons_path = bpy.utils.user_resource('SCRIPTS', path="addons")
        if os.path.commonprefix([addons_path, full_path]) == addons_path:
            if f.endswith(".py"):
                # we have to keep the actual addon scripts, otherwise it won't show up in Blender
                continue
            if f == "polib":
                # we have to keep the support lib, otherwise we'll get python ImportError exceptions
                continue

        print(f"Removing {full_path}", file=sys.stderr)
        if os.path.isdir(full_path):
            shutil.rmtree(full_path)
        else:
            os.remove(full_path)

    return new_path


def contains_object_duplicate_suffix(name: str) -> bool:
    pattern = re.compile(r"^\.[0-9]{3}$")
    return pattern.match(name[-4:])


def remove_object_duplicate_suffix(name: str) -> str:
    splitted_name = name.rsplit(".", 1)
    if len(splitted_name) == 1:
        return splitted_name[0]

    if splitted_name[1].isnumeric():
        return splitted_name[0]

    return name


def generate_unique_name(old_name: str, container: typing.Iterable[typing.Any]) -> str:
    # TODO: Unify this with renderset unique naming generation
    name_without_suffix = remove_object_duplicate_suffix(old_name)
    i = 1
    new_name = name_without_suffix
    while new_name in container:
        new_name = f"{name_without_suffix}.{i:03d}"
        i += 1

    return new_name


DuplicateFilter = typing.Callable[[bpy.types.ID], bool]


def is_duplicate_filtered(data: bpy.types.ID, filters: typing.Iterable[DuplicateFilter]) -> bool:
    filtered = False
    for filter_ in filters:
        if not filter_(data):
            filtered = True
            break

    return filtered


def remove_duplicate_node_groups(filters: typing.Iterable[DuplicateFilter]) -> None:
    to_remove = []

    for node_group in bpy.data.node_groups:
        if is_duplicate_filtered(node_group, filters):
            continue

        # ok, so it's a duplicate, let's figure out the "proper" node group
        orig_node_group_name = remove_object_duplicate_suffix(node_group.name)
        if orig_node_group_name in bpy.data.node_groups:
            orig_node_group = bpy.data.node_groups[orig_node_group_name]
            node_group.user_remap(orig_node_group)
            if node_group.users == 0:
                to_remove.append(node_group)
        else:
            # the original node group is gone, we should rename this one
            node_group.name = orig_node_group_name

    for node_group in to_remove:
        bpy.data.node_groups.remove(node_group)


def remove_duplicate_materials(filters: typing.Iterable[DuplicateFilter]) -> None:
    to_remove = []

    for obj in bpy.data.objects:
        for mat_slot in obj.material_slots:
            material = mat_slot.material
            if material is None:
                continue

            if is_duplicate_filtered(material, filters):
                continue

            # ok, so it's a duplicate, let's figure out the "proper" material
            orig_material_name = remove_object_duplicate_suffix(material.name)
            if orig_material_name in bpy.data.materials:
                orig_material = bpy.data.materials[orig_material_name]
                mat_slot.material = orig_material
                if material.users == 0:
                    to_remove.append(material)
            else:
                # the original material is gone, we should rename this one
                material.name = orig_material_name

    for mat in to_remove:
        bpy.data.materials.remove(mat)


def remove_duplicate_images(filters: typing.Iterable[DuplicateFilter]) -> None:
    to_remove = []

    for image in bpy.data.images:
        if is_duplicate_filtered(image, filters):
            continue

        # ok, so it's a duplicate, let's figure out the "proper" image
        orig_image_name = remove_object_duplicate_suffix(image.name)
        if orig_image_name in bpy.data.images:
            orig_image = bpy.data.images[orig_image_name]
            image.user_remap(orig_image)
            if image.users == 0:
                to_remove.append(image)
        else:
            # the original image is gone, we should rename this one
            image.name = orig_image_name

    for image in to_remove:
        bpy.data.images.remove(image)


def remove_duplicate_worlds(filters: typing.Iterable[DuplicateFilter]) -> None:
    to_remove = []

    for world in bpy.data.worlds:
        if is_duplicate_filtered(world, filters):
            continue

        orig_world_name = remove_object_duplicate_suffix(world.name)
        if orig_world_name in bpy.data.worlds:
            orig_world = bpy.data.worlds[orig_world_name]
            world.user_remap(orig_world)
            if world.users == 0:
                to_remove.append(world)
        else:
            world.name = orig_world_name

    for world in to_remove:
        bpy.data.worlds.remove(world)


def blender_cursor(cursor_name: str = 'WAIT'):
    """Decorator that sets a modal cursor in Blender to whatever the caller desires,
    then sets it back when the function returns. This is useful for long running
    functions or operators. Showing a WAIT cursor makes it less likely that the user
    will think that Blender froze.

    Unfortunately this can only be used in cases we control and only when 'context' is
    available.

    TODO: Maybe we could use bpy.context and drop the context requirement?
    """

    def cursor_decorator(fn):
        def wrapper(self, context: bpy.types.Context, *args, **kwargs):
            context.window.cursor_modal_set(cursor_name)
            try:
                return fn(self, context, *args, **kwargs)
            finally:
                context.window.cursor_modal_restore()

        return wrapper

    return cursor_decorator


def timeit(fn):
    def timed(*args, **kw):
        ts = time.time()
        result = fn(*args, **kw)
        te = time.time()
        print(f"{fn.__name__!r}  {(te - ts) * 1000:2.2f} ms")
        return result
    return timed


def timed_cache(**timedelta_kwargs):
    def _wrapper(f):
        update_delta = datetime.timedelta(**timedelta_kwargs)
        next_update = datetime.datetime.utcnow() + update_delta
        f = functools.lru_cache(None)(f)

        @functools.wraps(f)
        def _wrapped(*args, **kwargs):
            nonlocal next_update
            now = datetime.datetime.utcnow()
            if now >= next_update:
                f.cache_clear()
                next_update = now + update_delta
            return f(*args, **kwargs)
        return _wrapped
    return _wrapper


def xdg_open_file(path):
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.call(["open", path])
    else:
        subprocess.call(["xdg-open", path])
