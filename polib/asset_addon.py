#!/usr/bin/python3
# copyright (c) 2018- polygoniq xyz s.r.o.

import bpy
import bpy.utils.previews
import bmesh
import os
import os.path
import typing
import collections
import enum
import logging
logger = logging.getLogger(__name__)


if "linalg" not in locals():
    from . import linalg
    from . import utils
    from . import rigs_shared
else:
    import importlib
    linalg = importlib.reload(linalg)
    utils = importlib.reload(utils)
    rigs_shared = importlib.reload(rigs_shared)


PARTICLE_SYSTEM_PREFIX = "pps_"
PREVIEW_NOT_FOUND = "No-Asset-Found"


def get_name_category_map(previews_path: str) -> typing.Dict[str, str]:
    ret = {}
    for path, _, files in os.walk(previews_path):
        for file in files:
            filename, ext = os.path.splitext(file)
            if ext not in {".png", ".jpg"}:
                continue

            _, category = os.path.split(path)
            ret[filename] = category

    return ret


def list_categories(previews_path: str, previews_gray_path: typing.Optional[str], filters: typing.Optional[typing.Iterable[typing.Callable]] = None) -> typing.List[str]:
    ret = []
    categories = set(os.listdir(previews_path))
    if previews_gray_path is not None and os.path.isdir(previews_gray_path):
        categories.update(set(os.listdir(previews_gray_path)))

    for name in sorted(categories):
        filtered = False
        if filters is not None:
            for filter_ in filters:
                if not filter_(name):
                    filtered = True
                    break

        if filtered:
            continue

        ret.append(name)

    return ret


PreviewFilter = typing.Callable[[str], bool]


def expand_search_keywords(translator: typing.Dict[str, typing.Iterable[str]], keywords: typing.Iterable[str]) -> typing.Set[str]:
    ret = set()
    for keyword in keywords:
        keyword = keyword.lower()
        ret.add(keyword)
        ret.update(translator.get(keyword, []))
    return ret


def search_for_keywords(expanded_keywords: typing.Iterable[str], text: str) -> bool:
    match = False
    text_lower = text.lower()
    for keyword in expanded_keywords:
        if keyword.lower() in text_lower:
            match = True
            break

    return match


def search_by_keywords_filter(preview_basename: str, search_keywords: typing.Iterable[str], name_formatter: typing.Callable[[str], str]):
    if not search_keywords:
        return True

    nice_name = name_formatter(preview_basename)
    if not search_for_keywords(search_keywords, nice_name):
        # skipping because it was filtered out
        return False

    return True


def enum_property_set(data_block: bpy.types.bpy_struct, prop_name: str, value: int):
    """Default set function for enum properties"""
    data_block[prop_name] = value


def enum_property_get(
    data_block: bpy.types.bpy_struct,
    prop_name: str,
    items: typing.Iterable[bpy.types.EnumPropertyItem]
) -> int:
    """Default get function for enum properties that ensures validity of returned item"""
    assert len(items) > 0  # There should be one preview for not found state
    current_item = data_block.get(prop_name, 0)
    if current_item not in {i[4] for i in items}:
        return items[0][4]

    return current_item


def list_asset_previews(
        previews_path: str,
        previews_gray_path: typing.Optional[str],
        category: str,
        name_formatter: typing.Callable[[str], str],
        filters: typing.Iterable[PreviewFilter],
        telemetry: typing.Any):
    if not hasattr(list_asset_previews, "pcoll"):
        list_asset_previews.pcoll = bpy.utils.previews.new()

    ret = {"enum_items": [], "pcoll": list_asset_previews.pcoll}

    def process_preview_file(previews_path: str, category: str, preview_filename: str, i: int, i_base: int = 0) -> None:
        if not preview_filename.endswith((".jpg", ".png")):
            return

        full_path = os.path.join(previews_path, category, preview_filename)
        if not os.path.exists(full_path):
            telemetry.log_warning(f"{full_path} not found! Skipping this asset in the browser!")
            return

        preview_basename, _ = os.path.splitext(preview_filename)

        filtered = False
        for filter_ in filters:
            if not filter_(preview_basename):
                # filtered out
                filtered = True
                break

        if filtered:
            return

        if preview_basename in ret["pcoll"]:
            image = ret["pcoll"][preview_basename]
        else:
            image = ret["pcoll"].load(preview_basename, full_path, 'IMAGE')

        nice_name = name_formatter(preview_basename)
        ret["enum_items"].append((preview_basename, nice_name,
                                  preview_basename, image.icon_id, i + i_base))

    path = os.path.join(previews_path, category)
    path_gray = os.path.join(
        previews_gray_path, category) if previews_gray_path is not None else None

    if not os.path.isdir(path) and (path_gray is None or not os.path.isdir(path_gray)):
        # Add default error preview to give feedback to user if category was not populated
        ret["enum_items"].append((PREVIEW_NOT_FOUND, "Nothing found", "Nothing Found", 'X', 0))
        telemetry.log_warning(f"{path} not found! Skipping category!")
        return ret

    preview_filenames = sorted(os.listdir(path)) if os.path.isdir(path) else []
    for i, preview_filename in enumerate(preview_filenames):
        process_preview_file(previews_path, category, preview_filename, i, 0)

    if path_gray is not None and os.path.isdir(path_gray):
        i_gray_base = len(preview_filenames)

        gray_preview_filenames = sorted(os.listdir(path_gray))
        for i, preview_filename in enumerate(gray_preview_filenames):
            process_preview_file(previews_gray_path, category, preview_filename, i, i_gray_base)

    # Add at least one item, so we can represent that nothing was found
    if len(ret["enum_items"]) == 0:
        ret["enum_items"].append((PREVIEW_NOT_FOUND, "Nothing found", "Nothing Found", 'X', 0))
    return ret


def get_all_object_ancestors(obj: bpy.types.Object) -> typing.Set[bpy.types.Object]:
    """Returns given object's parent, the parent's parent, ...
    """

    ret = set()
    current = obj.parent
    while current is not None:
        ret.add(current)
        current = current.parent
    return ret


def filter_out_descendants_from_objects(
    objects: typing.Iterable[bpy.types.Object]
) -> typing.Set[bpy.types.Object]:
    """Given a list of objects (i.e. selected objects) this function will return only the
    roots. By roots we mean included objects that have no ancestor that is also contained
    in object.

    Example of use of this is when figuring out which objects to snap to ground. If you have
    a complicated selection of cars, their wheels, etc... you onlt want to snap the parent car
    body, not all objects.
    """

    all_objects = set(objects)

    ret = set()
    for obj in objects:
        ancestors = get_all_object_ancestors(obj)
        if len(all_objects.intersection(ancestors)) == 0:
            # this object has no ancestors that are also contained in objects
            ret.add(obj)

    return ret


def is_polygoniq_object(
    obj: bpy.types.Object,
    addon_name: typing.Optional[str] = None,
    include_editable: bool = True,
    include_linked: bool = True
) -> bool:
    if include_editable and obj.get("polygoniq_addon", None) is not None:
        # the object is editable and has custom properties
        return addon_name is None or obj.get("polygoniq_addon", None) == addon_name

    elif include_linked and obj.instance_collection is not None:
        # the object is linked and the custom properties are in the linked collection
        # in most cases there will be exactly one linked object but we want to play it
        # safe and will check all of them. if any linked object is a polygoniq object
        # we assume the whole instance collection is
        for linked_obj in obj.instance_collection.objects:
            if is_polygoniq_object(linked_obj, addon_name):
                return True

        return False


def find_polygoniq_root_objects(
    objects: typing.Iterable[bpy.types.Object],
    addon_name: typing.Optional[str] = None
) -> typing.Set[bpy.types.Object]:
    """Finds and returns polygoniq root objects in 'objects'.

    Returned objects are either root or their parent isn't polygoniq object.
    E. g. for 'objects' selected from hierarchy:
    Users_Empty -> Audi_R8 -> [Lights, Wheel1..N -> [Brakes]], this returns Audi_R8.
    """

    traversed_objects = set()
    root_objects = set()

    for obj in objects:
        if obj in traversed_objects:
            continue

        current_obj = obj
        while True:
            if current_obj in traversed_objects:
                break

            if current_obj.parent is None:
                if is_polygoniq_object(current_obj, addon_name):
                    root_objects.add(current_obj)
                break

            if is_polygoniq_object(current_obj, addon_name) and not is_polygoniq_object(current_obj.parent, addon_name):
                root_objects.add(current_obj)
                break

            traversed_objects.add(current_obj)
            current_obj = current_obj.parent

    return root_objects


def get_polygoniq_objects(
    objects: typing.Iterable[bpy.types.Object],
    addon_name: typing.Optional[str] = None,
    include_editable: bool = True,
    include_linked: bool = True
) -> typing.Generator[bpy.types.Object, None, None]:
    """Returns generator of objects that contain polygoniq_addon property
    """
    for obj in objects:
        if is_polygoniq_object(obj, addon_name, include_editable, include_linked):
            yield obj


def get_addon_install_path(addon_name: str) -> typing.Optional[str]:
    addon = bpy.context.preferences.addons.get(addon_name, None)
    if addon is None:
        return None

    return getattr(addon.preferences, "install_path", None)


def get_addons_install_paths(addon_names: typing.List[str], short_names: bool = False) -> typing.Dict[str, str]:
    install_paths = {}
    for addon_name in addon_names:
        install_path = get_addon_install_path(addon_name)
        if install_path is None:
            continue
        if short_names:
            short_name, _ = addon_name.split("_", 1)
            install_paths[short_name] = install_path
        else:
            install_paths[addon_name] = install_path

    return install_paths


def get_installed_polygoniq_asset_addons() -> typing.Dict[str, bpy.types.Addon]:
    polygoniq_addons = {}
    # We keep track of basenames to detect multiple installations of addons
    found_base_names = set()
    asset_addon_base_names = ("botaniq", "traffiq", "materialiq", "waterial")
    for name, addon in bpy.context.preferences.addons.items():
        for base_name in asset_addon_base_names:
            if not name.startswith(base_name):
                continue

            if base_name in found_base_names:
                raise RuntimeError(
                    f"Multiple versions of '{base_name}' addon exist! "
                    "Please disable versions you don't want to use!"
                )

            found_base_names.add(base_name)
            polygoniq_addons[name] = addon

    return polygoniq_addons


class TiqAssetPart(enum.Enum):
    Body = 'Body'
    Lights = 'Lights'
    Wheel = 'Wheel'
    Brake = 'Brake'


def is_traffiq_asset_part(obj: bpy.types.Object, part: TiqAssetPart) -> bool:
    addon_name = obj.get("polygoniq_addon", "")
    if addon_name != "traffiq":
        return False

    obj_name = utils.remove_object_duplicate_suffix(obj.name)
    if part in {TiqAssetPart.Body, TiqAssetPart.Lights}:
        splitted_name = obj_name.rsplit("_", 1)
        if len(splitted_name) != 2:
            return False

        _, obj_part_name = splitted_name
        if obj_part_name != part.name:
            return False
        return True

    elif part in {TiqAssetPart.Wheel, TiqAssetPart.Brake}:
        splitted_name = obj_name.rsplit("_", 3)
        if len(splitted_name) != 4:
            return False

        _, obj_part_name, position, wheel_number = splitted_name
        if obj_part_name != part.name:
            return False
        if position not in {"FL", "FR", "BL", "BR", "F", "B"}:
            return False
        if not wheel_number.isdigit():
            return False
        return True

    return False


DecomposedCarType = typing.Tuple[bpy.types.Object, bpy.types.Object,
                                 bpy.types.Object, typing.List[bpy.types.Object], typing.List[bpy.types.Object]]


def get_root_object_of_asset(asset: bpy.types.Object) -> typing.Optional[bpy.types.Object]:
    """Returns the root linked object if given a linked asset (instanced collection empty).
    Returns the object itself if given an editable asset. In case there are multiple roots
    or no roots at all it returns None and logs a warning.
    """

    if asset.instance_type == 'COLLECTION':
        # we have to iterate through objects in the collection and return the one
        # that has no parent.

        root_obj = None
        for obj in asset.instance_collection.objects:
            if obj.parent is None:
                if root_obj is not None:
                    logger.warning(
                        f"Found multiple root objects in the given collection instance "
                        f"empty (name='{asset.name}')"
                    )
                    return None

                root_obj = obj

        if root_obj is None:
            logger.warning(
                f"Failed to find the root object of a given collection instance empty "
                f"(name='{asset.name}')"
            )

        return root_obj

    else:
        # given object is editable
        return asset


def get_entire_object_hierachy(obj: bpy.types.Object) -> typing.Iterable[bpy.types.Object]:
    """Returns object hierarchy (the object itself and all descendants) in case the object is
    editable. In case the object is instanced it looks through the instance_collection.objects
    and returns all descendants from there.

    Example: If you pass a traffiq car object it will return body, wheels and lights.
    """
    ret = []
    for child in obj.children:
        ret.extend(get_entire_object_hierachy(child))

    if obj.instance_type == 'COLLECTION':
        for col_obj in obj.instance_collection.objects:
            ret.append(col_obj)
    else:
        ret.append(obj)

    return ret


def decompose_traffiq_vehicle(obj: bpy.types.Object) -> DecomposedCarType:
    if obj is None:
        return None, None, None, [], []

    root_object = get_root_object_of_asset(obj)
    body = None
    lights = None
    wheels = []
    brakes = []

    hierarchy_objects = get_entire_object_hierachy(obj)
    for hierarchy_obj in hierarchy_objects:
        if is_traffiq_asset_part(hierarchy_obj, TiqAssetPart.Body):
            # there should be only one body
            assert body is None
            body = hierarchy_obj
        elif is_traffiq_asset_part(hierarchy_obj, TiqAssetPart.Lights):
            # there should be only one lights
            assert lights is None
            lights = hierarchy_obj
        elif is_traffiq_asset_part(hierarchy_obj, TiqAssetPart.Wheel):
            wheels.append(hierarchy_obj)
        elif is_traffiq_asset_part(hierarchy_obj, TiqAssetPart.Brake):
            brakes.append(hierarchy_obj)

    return root_object, body, lights, wheels, brakes


def find_traffiq_asset_parts(obj: bpy.types.Object, part: TiqAssetPart) -> typing.Iterable[bpy.types.Object]:
    """Find all asset parts of a specific type."""

    for hierarchy_obj in get_entire_object_hierachy(obj):
        if is_traffiq_asset_part(hierarchy_obj, part):
            yield hierarchy_obj


def can_asset_change_color(obj: bpy.types.Object) -> bool:
    """Returns true if color changing is supported by changing the obj.color value.
    Vehicles, airplanes, boats and several other assets in traffiq support this.

    This function works with both linked and editable assets.
    """

    # only traffiq assets support changing color for now
    if not is_polygoniq_object(obj, "traffiq"):
        return False

    body_candidates = list(find_traffiq_asset_parts(obj, TiqAssetPart.Body))
    if len(body_candidates) == 0:
        return False
    if len(body_candidates) > 1:
        logger.warning(f"{obj.name} has multiple asset parts of type '_Body'.")
        return False

    return True


def get_asset_color_object(obj: bpy.types.Object) -> bpy.types.Object:
    """Returns object from asset hierarchy that is responsible for changing vehicle's color.
    """
    # asset is instanced
    if obj.instance_type == 'COLLECTION':
        return obj

    # asset is editable
    body_candidates = list(find_traffiq_asset_parts(obj, TiqAssetPart.Body))
    if len(body_candidates) == 0:
        return None
    if len(body_candidates) > 1:
        logger.warning(f"{obj.name} has multiple asset parts of type '_Body'.")
        return None

    return body_candidates[0]


def create_instanced_object(collection_name: str) -> bpy.types.Object:
    """Creates empty and sets the instance collection to one with 'collection_name'.

    This is similar behaviour to bpy.ops.collection_instance_add(collection=collection_name),
    but it is faster, because it doesn't include bpy.ops overhead. Collection 'collection_name'
    has to exist in bpy.data.collections before call of this function.
    """

    assert collection_name in bpy.data.collections
    collection = bpy.data.collections[collection_name]
    instance_obj = bpy.data.objects.new(collection_name, None)
    instance_obj.instance_type = 'COLLECTION'
    instance_obj.instance_collection = collection
    # take object color from the first object in the collection
    # this is necessary for botaniq's seasons
    for obj in collection.all_objects:
        instance_obj.color = obj.color
        break
    return instance_obj


def traffiq_link_asset(
        context: bpy.types.Context,
        asset_name: str,
        blend_path: str,
        parent_collection: bpy.types.Collection,
        random_color: bool = False,
        custom_color: typing.Optional[typing.Tuple[float, float, float]] = None,
        lights_support: bool = False) -> typing.Optional[bpy.types.Object]:
    root_collection_name = None
    lights_collection_name = None
    with bpy.data.libraries.load(blend_path, link=True) as (data_from, data_to):
        data_to.collections = data_from.collections
        assert len(data_to.collections) >= 1
        for collection_name in data_to.collections:
            if collection_name == asset_name:
                assert root_collection_name is None
                root_collection_name = collection_name
            elif collection_name.endswith("_Lights"):
                assert lights_collection_name is None
                lights_collection_name = collection_name

    root_empty = None
    if root_collection_name is not None:
        root_empty = create_instanced_object(root_collection_name)
        root_empty.location = context.scene.cursor.location

    if root_empty is None:
        return None

    # TODO: possibly remove this because it's at the body empty now
    if not random_color and custom_color is not None:
        if custom_color == (1.0, 1.0, 1.0):
            custom_color = (0.99, 0.99, 0.99)
        root_empty.color = (custom_color[0], custom_color[1], custom_color[2], 1.0)

    collection_add_object(parent_collection, root_empty)

    if lights_support and lights_collection_name is not None:
        lights_empty = create_instanced_object(lights_collection_name)
        lights_empty.name = asset_name + "_Lights"
        lights_empty.parent = root_empty
        # default to lights OFF
        lights_empty.color = (0.0, 0.0, 0.0, 1.0)
        collection_add_object(parent_collection, lights_empty)

    return root_empty


def traffiq_lights_hierarchy_comparator(
        obj_name: str,
        root_obj_name: typing.Optional[str] = None) -> bool:
    if root_obj_name is None:
        return False

    sole_obj_name = utils.remove_object_duplicate_suffix(obj_name)
    sole_root_name = utils.remove_object_duplicate_suffix(root_obj_name)
    return sole_obj_name.startswith(sole_root_name) and sole_obj_name.endswith("_Lights")


def generic_link_asset(
    context: bpy.types.Context,
    asset_name: str,
    blend_path: str,
    parent_collection: bpy.types.Collection
) -> typing.Optional[bpy.types.Object]:
    """Links root collection from 'blend_path' to children of 'parent_collection'"""
    root_collection_name = None
    with bpy.data.libraries.load(blend_path, link=True) as (data_from, data_to):
        data_to.collections = data_from.collections
        assert len(data_to.collections) >= 1
        root_collection_name = data_to.collections[0]

    root_empty = None
    if root_collection_name is not None:
        root_empty = create_instanced_object(root_collection_name)
        root_empty.location = context.scene.cursor.location

    if root_empty is None:
        return None

    collection_add_object(parent_collection, root_empty)

    return root_empty


def make_selection_linked(context: bpy.types.Context, telemetry):
    assert telemetry is not None
    addon_install_paths = get_addons_install_paths(
        get_installed_polygoniq_asset_addons().keys(),
        short_names=True
    )
    previous_selection = [obj.name for obj in context.selected_objects]
    previous_active_object_name = context.active_object.name if context.active_object else None

    converted_objects = []
    for obj in find_polygoniq_root_objects(context.selected_objects):
        if obj.instance_type == 'COLLECTION':
            continue

        path_property = obj.get("polygoniq_addon_blend_path", None)
        if path_property is None:
            continue

        # Particle systems are skipped. After converting to editable
        # all instances of particle system are separate objects. It
        # is not easy to decide which object belonged to what preset.
        if path_property.startswith("blends_280_particles/"):
            continue

        addon_property = obj.get("polygoniq_addon", None)
        if addon_property is None:
            continue

        install_path = addon_install_paths.get(addon_property, None)
        if install_path is None:
            telemetry.log_warning(
                f"Obj {obj.name} contains property: {addon_property} but addon is not installed!")
            continue

        asset_path = os.path.join(install_path, os.path.normpath(path_property))
        if not os.path.isfile(asset_path):
            telemetry.log_warning(
                f"Cannot link {obj.name} from {asset_path} because "
                "it doesn't exist, perhaps the asset isn't in this version anymore.")
            continue

        asset_name, _ = os.path.splitext(os.path.basename(path_property))

        instance_root = None
        old_model_matrix = obj.matrix_world.copy()
        old_collections = list(obj.users_collection)
        old_color = tuple(obj.color)
        old_lights_state = find_object_in_hierarchy(
            obj,
            traffiq_lights_hierarchy_comparator
        ) is not None
        old_parent = obj.parent

        # This way old object names won't interfere with the new ones
        hierarchy_objects = get_hierarchy(obj)
        for hierarchy_obj in hierarchy_objects:
            hierarchy_obj.name = utils.generate_unique_name(
                f"del_{hierarchy_obj.name}", bpy.data.objects)

        if addon_property == "traffiq":
            if can_asset_change_color(obj):
                old_color = get_asset_color_object(obj).color
            instance_root = traffiq_link_asset(
                context,
                asset_name,
                asset_path,
                old_collections[0],
                old_color == (1.0, 1.0, 1.0),
                old_color,
                old_lights_state
            )
        elif addon_property in {"botaniq", "waterial"}:
            instance_root = generic_link_asset(
                context,
                asset_name,
                asset_path,
                old_collections[0]
            )
        else:
            telemetry.log_warning(f"Unexpected addon property '{addon_property}' found")
            continue

        if instance_root is None:
            telemetry.log_error(f"Failed to link asset {obj} with "
                                f"{addon_property}, instance is None")
            continue

        instance_root.matrix_world = old_model_matrix
        instance_root.parent = old_parent

        for coll in old_collections:
            if instance_root.name not in coll.objects:
                coll.objects.link(instance_root)

        converted_objects.append(instance_root)

        bpy.data.batch_remove(hierarchy_objects)

    for obj_name in previous_selection:
        obj = context.view_layer.objects.get(obj_name, None)
        # Linked version doesn't neccessary contain the same objects
        # e. g. traffiq linked version doesn't contain wheels, brakes, ...
        if obj is not None:
            obj.select_set(True)

    if previous_active_object_name is not None and \
       previous_active_object_name in context.view_layer.objects:
        context.view_layer.objects.active = bpy.data.objects[previous_active_object_name]

    return converted_objects


def make_selection_editable(context: bpy.types.Context, delete_base_empty: bool, keep_selection: bool = True, keep_active: bool = True) -> typing.List[str]:
    def apply_botaniq_particle_system_modifiers(obj: bpy.types.Object):
        for child in obj.children:
            apply_botaniq_particle_system_modifiers(child)

        for modifier in obj.modifiers:
            if modifier.type != 'PARTICLE_SYSTEM' or not modifier.name.startswith(PARTICLE_SYSTEM_PREFIX):
                continue

            clear_selection(context)
            obj.select_set(True)
            bpy.ops.object.duplicates_make_real(use_base_parent=True, use_hierarchy=True)
            obj.select_set(False)

            # Remove collection with unused origin objects previously used for particle system
            if modifier.name in bpy.data.collections:
                collection = bpy.data.collections[modifier.name]
                particle_origins = [obj for obj in collection.objects if obj.users == 1]
                bpy.data.batch_remove(particle_origins)
                if len(collection.objects) == 0:
                    bpy.data.collections.remove(collection)

            obj.modifiers.remove(modifier)

    InstancedObjectInfo = typing.Tuple[bpy.types.Object, bpy.types.Collection,
                                       str, typing.Tuple[float, float, float, float]]

    def find_instanced_collection_objects(obj: bpy.types.Object, instanced_collection_objects: typing.Dict[str, InstancedObjectInfo]):
        for child in obj.children:
            find_instanced_collection_objects(child, instanced_collection_objects)

        if obj.instance_type == 'COLLECTION':
            if obj.name not in instanced_collection_objects:
                instanced_collection_objects[obj.name] = (
                    obj, obj.instance_collection, obj.parent.name if obj.parent else None, obj.color)

    def copy_polygoniq_custom_props_from_children(obj: bpy.types.Object) -> None:
        """Tries to copy Polygoniq custom properties from children to 'obj'.

        Tries to find child with all polygoniq custom properties
        if such a child exists, values of its properties are copied to 'obj'.
        """
        for child in obj.children:
            copyright = child.get("copyright", None)
            polygoniq_addon = child.get("polygoniq_addon", None)
            polygoniq_blend_path = child.get("polygoniq_addon_blend_path", None)
            if all(prop is not None for prop in [copyright, polygoniq_addon, polygoniq_blend_path]):
                obj["copyright"] = copyright
                obj["polygoniq_addon"] = polygoniq_addon
                obj["polygoniq_addon_blend_path"] = polygoniq_blend_path
                return

    def get_mesh_to_objects_map(obj: bpy.types.Object, result: typing.DefaultDict[str, bpy.types.Object]):
        for child in obj.children:
            get_mesh_to_objects_map(child, result)

        if obj.type == 'MESH':
            original_mesh_name = utils.remove_object_duplicate_suffix(obj.data.name)
            result[original_mesh_name].append(obj)

    def get_material_to_slots_map(obj: bpy.types.Object, result: typing.DefaultDict[str, bpy.types.MaterialSlot]):
        for child in obj.children:
            get_material_to_slots_map(child, result)

        if obj.type == 'MESH':
            for material_slot in obj.material_slots:
                if material_slot.material is not None:
                    original_material_name = utils.remove_object_duplicate_suffix(
                        material_slot.material.name)
                    result[original_material_name].append(material_slot)

    def get_armatures_to_objects_map(obj: bpy.types.Object, result: typing.DefaultDict[str, bpy.types.Object]):
        for child in obj.children:
            get_armatures_to_objects_map(child, result)

        if obj.type == 'ARMATURE':
            original_armature_name = utils.remove_object_duplicate_suffix(obj.data.name)
            result[original_armature_name].append(obj)

    GetNameToUsersMapCallable = typing.Callable[[
        bpy.types.Object, typing.DefaultDict[str, bpy.types.ID]], None]

    def make_data_blocks_unique_per_object(obj: bpy.types.Object, get_data_to_struct_map: GetNameToUsersMapCallable, data_block_name: str):
        data_blocks_to_owner_structs = collections.defaultdict(list)
        get_data_to_struct_map(obj, data_blocks_to_owner_structs)

        for owner_structs in data_blocks_to_owner_structs.values():
            if len(owner_structs) == 0:
                continue

            first_data_block = getattr(owner_structs[0], data_block_name)
            if first_data_block.library is None and first_data_block.users == len(owner_structs):
                continue

            # data block is linked from library or it is used outside of object 'obj' -> create copy
            data_block_duplicate = first_data_block.copy()
            for owner_struct in owner_structs:
                setattr(owner_struct, data_block_name, data_block_duplicate)

    selected_objects_names = [obj.name for obj in context.selected_objects]
    prev_active_object_name = context.active_object.name if context.active_object else None

    instanced_collection_objects = {}
    for obj in context.selected_objects:
        find_instanced_collection_objects(obj, instanced_collection_objects)

    for obj_name in selected_objects_names:
        if obj_name in bpy.data.objects:
            apply_botaniq_particle_system_modifiers(bpy.data.objects[obj_name])

    # origin objects from particle systems were removed from scene
    selected_objects_names = [
        obj_name for obj_name in selected_objects_names if obj_name in bpy.data.objects]

    clear_selection(context)
    for instance_object, _, _, _ in instanced_collection_objects.values():
        # Operator duplicates_make_real converts each instance collection to empty (base parent) and its contents,
        # we change the name of the instance collection object (which becomes the empty) so it doesn't clash
        # with the naming of the actual objects (and doesn't increment duplicate suffix).
        # To keep track of what was converted and to not mess up names of objects
        # we use the '[0-9]+bp_' prefix for the base parent
        i = 0
        name = f"{i}bp_" + instance_object.name
        while name in bpy.data.objects:
            i += 1
            name = f"{i}bp_" + instance_object.name

        instance_object.name = name
        instance_object.select_set(True)
        bpy.ops.object.duplicates_make_real(use_base_parent=True, use_hierarchy=True)
        instance_object.select_set(False)

    for obj, instance_collection, parent_name, prev_color in instanced_collection_objects.values():
        assert obj is not None

        for child in obj.children:
            child.color = prev_color

        # reorder the hierarchy in following way (car example):
        # base_parent_CAR -> [CAR, base_parent_CAR_Lights, WHEEL1..N -> [CAR_Lights]] to CAR -> [CAR_Lights, WHEEL1..N]
        if parent_name is not None and parent_name in bpy.data.objects:
            parent = bpy.data.objects[parent_name]
            for child in obj.children:
                # after setting parent object here, child.parent_type is always set to 'OBJECT'
                child.parent = parent
                child_source_name = utils.remove_object_duplicate_suffix(child.name)
                if child_source_name in instance_collection.objects and \
                        instance_collection.objects[child_source_name].parent is not None:
                    # set parent_type from source blend, for example our _Lights need to have parent_type = 'BONE'
                    child.parent_type = instance_collection.objects[child_source_name].parent_type
                    child.matrix_local = instance_collection.objects[child_source_name].matrix_local
            bpy.data.objects.remove(obj)
            continue

        if delete_base_empty:
            if len(obj.children) > 1:
                # instanced collection contained multiple top-level objects, keep base empty as container
                splitted_name = obj.name.split("_", 1)
                if len(splitted_name) == 2:
                    obj.name = splitted_name[1]
                # empty parent newly created in duplicates_make_real does not have polygoniq custom properties
                copy_polygoniq_custom_props_from_children(obj)

            else:
                # remove the parent from children which were not reparented above
                # if they were reparented they are no longer in obj.children and we can
                # safely delete the base parent
                for child in obj.children:
                    child.parent = None
                    child.matrix_world = obj.matrix_world.copy()
                bpy.data.objects.remove(obj)

    selected_objects = []
    for obj_name in selected_objects_names:
        if obj_name not in bpy.data.objects:
            logger.error(f"Previously selected object: {obj_name} is no longer in bpy.data")
            continue

        obj = bpy.data.objects[obj_name]
        # Create copy of meshes shared with other objects or linked from library
        make_data_blocks_unique_per_object(obj, get_mesh_to_objects_map, "data")
        # Create copy of materials shared with other objects or linked from library
        make_data_blocks_unique_per_object(obj, get_material_to_slots_map, "material")
        # Create copy of armature data shared with other objects or linked from library
        make_data_blocks_unique_per_object(obj, get_armatures_to_objects_map, "data")

        # Blender operator duplicates_make_real doesn't append animation data with drivers.
        # Thus we have to create those drivers dynamically based on bone names.
        if rigs_shared.is_object_rigged(obj):
            # set object as active to be able to go into POSE mode
            context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode='POSE')
            driver_creator = rigs_shared.RigDrivers(obj)
            driver_creator.create_all_drivers()
            bpy.ops.object.mode_set(mode='OBJECT')

        # Make sure color of traffiq assets doesn't change after converting to editable.
        # Only 'obj' has color of initially linked object. Find object from asset hierarchy
        # that affects asset's color and set it to color of previously linked object.
        if can_asset_change_color(obj):
            asset_color_obj = get_asset_color_object(obj)
            asset_color_obj.color = obj.color

        if keep_selection:
            selected_objects.append(obj_name)
            obj.select_set(True)

    if keep_active and prev_active_object_name is not None:
        if prev_active_object_name in bpy.data.objects:
            context.view_layer.objects.active = bpy.data.objects[prev_active_object_name]

    return selected_objects


def calculate_mesh_area(obj: bpy.types.Object, include_weight: bool = False):
    mesh = obj.data
    try:
        if obj.mode == "EDIT":
            bm = bmesh.from_edit_mesh(mesh)
        else:
            bm = bmesh.new()
            bm.from_mesh(mesh)

        bm.transform(obj.matrix_world)
        if include_weight:
            vg = obj.vertex_groups.active
            mesh_area = 0
            for face in bm.faces:
                f_area = face.calc_area()
                weighted_verts = 0
                weight = 0
                for v in face.verts:
                    # heavy approach, but we don't know whether i vertex is in the group :(
                    try:
                        weight += vg.weight(v.index)
                        weighted_verts += 1
                    except:
                        pass
                if weighted_verts > 0:
                    mesh_area += (weight / weighted_verts) * f_area
        else:
            mesh_area = sum(f.calc_area() for f in bm.faces)

    finally:
        bm.free()

    return mesh_area


HierarchyNameComparator = typing.Callable[[str, typing.Optional[str]], bool]


def find_object_in_hierarchy(
    root_obj: bpy.types.Object,
    name_comparator: HierarchyNameComparator,
) -> typing.Optional[bpy.types.Object]:
    # We don't use get_hierarchy function, because here we can return the desired
    # object before going through the whole hierarchy
    def search_hierarchy(parent_obj: bpy.types.Object) -> typing.Optional[bpy.types.Object]:
        if name_comparator(parent_obj.name, root_obj.name):
            return parent_obj

        for obj in parent_obj.children:
            candidate = search_hierarchy(obj)
            if candidate is not None:
                return candidate

        return None

    return search_hierarchy(root_obj)


def get_hierarchy(root):
    """Gatchers children of 'root' recursively
    """

    assert hasattr(root, "children")
    ret = [root]
    for child in root.children:
        ret.extend(get_hierarchy(child))

    return ret


def collection_get(context, name, parent=None):
    scene_collections = get_hierarchy(context.scene.collection)
    for coll in scene_collections:
        if utils.remove_object_duplicate_suffix(coll.name) == name:
            return coll

    coll = bpy.data.collections.new(name)
    if parent is None:
        context.scene.collection.children.link(coll)
    else:
        parent.children.link(coll)

    return coll


def collection_add_object(collection: bpy.types.Collection, obj: bpy.types.Object):
    """Unlinks 'obj' from all collections and links it into 'collection'
    """

    for coll in obj.users_collection:
        coll.objects.unlink(obj)

    collection.objects.link(obj)


def copy_object_hierarchy(root_obj: bpy.types.Object) -> bpy.types.Object:
    """
    Copies 'root_obj' and its hierarchy while preserving parenting, returns the root copy
    """

    def copy_hierarchy(obj: bpy.types.Object, parent: bpy.types.Object):
        obj_copy = obj.copy()
        obj_copy.parent = parent
        for child in obj.children:
            copy_hierarchy(child, obj_copy)

    root_obj_copy = root_obj.copy()
    for obj in root_obj.children:
        copy_hierarchy(obj, root_obj_copy)

    return root_obj_copy


def collection_link_hierarchy(collection: bpy.types.Collection, root_obj: bpy.types.Object):
    """Links 'root_obj' and its hierarachy to 'collection' and unlinks it from all other collections
    """

    for obj in get_hierarchy(root_obj):
        for coll in obj.users_collection:
            coll.objects.unlink(obj)
        collection.objects.link(obj)


def collection_unlink_hierarchy(collection: bpy.types.Collection, root_obj: bpy.types.Object):
    """Unlinks 'root_obj' and it's hierarchy from 'collection'
    """

    for obj in get_hierarchy(root_obj):
        collection.objects.unlink(obj)


def find_layer_collection(
        view_layer_root: bpy.types.LayerCollection,
        target: bpy.types.Collection) -> typing.Optional[bpy.types.LayerCollection]:
    """Finds corresponding LayerCollection from 'view_layer_coll' hierarchy
    which contains 'target' collection.
    """

    if view_layer_root.collection == target:
        return view_layer_root

    for layer_child in view_layer_root.children:
        found_layer_collection = find_layer_collection(layer_child, target)
        if found_layer_collection is not None:
            return found_layer_collection

    return None


def clear_selection(context: bpy.types.Context):
    for obj in context.selected_objects:
        obj.select_set(False)


def get_top_level_material_nodes_with_name(obj: bpy.types.Object, node_name: str) -> typing.Iterable[bpy.types.Node]:
    """Searches for top level nodes or node groups = not nodes nested in other node groups.

    Raise exception if 'obj' is instanced collection. If linked object links materials from another
    blend then Blender API doesn't allow us easily access these materials. We would be able only
    to access materials that are local inside blend of linked object. This could be confusing
    behavior of this function, so this function doesn't search for any nodes in linked objects.
    """
    assert obj.instance_collection != 'COLLECTION'

    for material_slot in obj.material_slots:
        if material_slot.material is None:
            continue
        for node in material_slot.material.node_tree.nodes:
            if node.type == 'GROUP':
                if node.node_tree.name == node_name:
                    yield node
            else:
                if node.name == node_name:
                    yield node


def append_modifiers_from_library(
    modifier_container_name: str,
    library_path: str,
    target_objs: typing.Iterable[bpy.types.Object]
) -> None:
    """Add all modifiers from object with given name in given .blend library to 'target_objects'.

    It doesn't copy complex and readonly properties, e.g. properties that are driven by FCurve.
    """
    if modifier_container_name not in bpy.data.objects:
        with bpy.data.libraries.load(library_path) as (data_from, data_to):
            assert modifier_container_name in data_from.objects
            data_to.objects = [modifier_container_name]

    assert modifier_container_name in bpy.data.objects
    modifier_container = bpy.data.objects[modifier_container_name]

    for obj in target_objs:
        for src_modifier in modifier_container.modifiers:
            assert src_modifier.name not in obj.modifiers
            dest_modifier = obj.modifiers.new(src_modifier.name, src_modifier.type)

            # collect names of writable properties
            properties = [p.identifier for p in src_modifier.bl_rna.properties if not p.is_readonly]

            # copy those properties
            for prop in properties:
                setattr(dest_modifier, prop, getattr(src_modifier, prop))


def can_have_materials_assigned(obj: bpy.types.Object) -> bool:
    """Checks whether given object can have materials assigned. We check for multiple
    things: type of the object and the availability of material_slots.
    """

    # TODO: In theory checking the availability of material_slots is not necessary, all these
    # object types should have it. I check for it to avoid exceptions and errors in our code.

    return obj.type in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'GPENCIL', 'VOLUME'} \
        and hasattr(obj, "material_slots")
