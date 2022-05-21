bl_info = {
    "name": "Speedups",
    "author": "Andrej Tetkić",
    "version": (1, 0),
    "blender": (2, 90, 0),
    "location": "",
    "description": "Gives you shortcuts to do some simple stuff to make workflow faster",
    "warning": "",
    "doc_url": "",
    "category": "Shortcuts",
}

import bpy
from. import addon_updater_ops

from bpy.types import Menu, Panel, Operator, Header
import mathutils
from bpy import context
from . import polib
import addon_utils
import Speedups


####PREFERENCES#####

@addon_updater_ops.make_annotations
class Preferences(bpy.types.AddonPreferences):
    bl_idname = __name__
    
    auto_check_update = bpy.props.BoolProperty(
		name="Auto-check for Update",
		description="If enabled, auto-check for updates using an interval",
		default=False)

    updater_interval_months = bpy.props.IntProperty(
		name='Months',
		description="Number of months between checking for updates",
		default=0,
		min=0)

    updater_interval_days = bpy.props.IntProperty(
		name='Days',
		description="Number of days between checking for updates",
		default=7,
		min=0,
		max=31)

    updater_interval_hours = bpy.props.IntProperty(
		name='Hours',
		description="Number of hours between checking for updates",
		default=0,
		min=0,
		max=23)

    updater_interval_minutes = bpy.props.IntProperty(
		name='Minutes',
		description="Number of minutes between checking for updates",
		default=0,
		min=0,
		max=59)
    
    
    
    def draw(self, context):
        layout = self.layout
        
        mainrow = layout.row()
        col = mainrow.column()

        
        
        #row = layout.row()
        #row.label(text="Things that this addon does:")
        #row = layout.row()
        #row = layout.row()
        #row.label(text="    -Draws 3 new button for quickly switching between shader editor, timeline and graph editor")
        #row = layout.row()
        #row.label(text="    -Adds a pie menu that has option to add empty at selected object/vertex/edge/face, to move object origin at selected vertex/edge/face and more [hotkey - Shift Q]")
        #row = layout.row()
        #row.label(text="    -Add Reference Man in Add > Mesh > Add Reference Man")
        
        
        addon_updater_ops.update_settings_ui(self, context, col)
        
        addon_updater_ops.update_notice_box_ui(self, context)
        
        
        
        
######################################################  Shader thing  ################################################   

class Switch_To_OT_ShaderNodeTree(Operator):
    bl_idname = "screen.switch_area_type"
    bl_label = ""
    
    def execute(self, context):
        bpy.context.area.ui_type = 'ShaderNodeTree'
        return {'FINISHED'}
    
class Switch_To_OT_TIMELINE(Operator):
    bl_idname = "screen.switch_area_type_time"
    bl_label = ""
    
    def execute(self, context):
        bpy.context.area.ui_type = 'TIMELINE'
        return {'FINISHED'}

class Switch_To_OT_GRAPH_EDITOR(Operator):
    bl_idname = "screen.switch_area_type_graph"
    bl_label = ""
    
    def execute(self, context):
        bpy.context.area.ui_type = 'FCURVES'
        return {'FINISHED'}  
        
#####TIMELINE#####

class TIME_MT_editor_menus(Menu):
    bl_idname = "TIME_MT_editor_menus"
    bl_label = ""

    def draw(self, context):
        layout = self.layout
        horizontal = (layout.direction == 'VERTICAL')
        st = context.space_data
        if horizontal:
            row = layout.row()
            sub = row.row(align=True)
        else:
            sub = layout

        sub.popover(
            panel="TIME_PT_playback",
            text="Playback",
        )
        sub.popover(
            panel="TIME_PT_keyframing_settings",
            text="Keying",
        )

        # Add a separator to keep the popover button from aligning with the menu button.
        sub.separator(factor=0.4)

        if horizontal:
            sub = row.row(align=True)

        sub.menu("TIME_MT_view")
        if st.show_markers:
            sub.menu("TIME_MT_marker")
            
        sub.separator(factor=0.4)
        sub.operator("screen.switch_area_type", icon="NODE_MATERIAL")
        
        sub.separator(factor=0.4)
        sub.operator("screen.switch_area_type_time", icon="TIME")
        
        sub.separator(factor=0.4)
        sub.operator("screen.switch_area_type_graph", icon="GRAPH")
            
####GRAPH#####

class GRAPH_MT_editor_menus(Menu):
    bl_idname = "GRAPH_MT_editor_menus"
    bl_label = ""

    def draw(self, context):
        st = context.space_data
        layout = self.layout
        layout.menu("GRAPH_MT_view")
        layout.menu("GRAPH_MT_select")
        if st.mode != 'DRIVERS' and st.show_markers:
            layout.menu("GRAPH_MT_marker")
        layout.menu("GRAPH_MT_channel")
        layout.menu("GRAPH_MT_key")
        
        #sub = row.row(align=True)
        layout.separator(factor=0.4)
        layout.operator("screen.switch_area_type", icon="NODE_MATERIAL")
        
        layout.separator(factor=0.4)
        layout.operator("screen.switch_area_type_time", icon="TIME")
        
        layout.separator(factor=0.4)
        layout.operator("screen.switch_area_type_graph", icon="GRAPH")
        
        
        scene = context.scene
        tool_settings = context.tool_settings
        screen = context.screen

        layout.separator_spacer()

        row = layout.row(align=True)
        row.prop(tool_settings, "use_keyframe_insert_auto", text="", toggle=True)
        sub = row.row(align=True)
        sub.active = tool_settings.use_keyframe_insert_auto
        sub.popover(
            panel="TIME_PT_auto_keyframing",
            text="",
        )

        row = layout.row(align=True)
        row.operator("screen.frame_jump", text="", icon='REW').end = False
        row.operator("screen.keyframe_jump", text="", icon='PREV_KEYFRAME').next = False
        if not screen.is_animation_playing:
            # if using JACK and A/V sync:
            #   hide the play-reversed button
            #   since JACK transport doesn't support reversed playback
            if scene.sync_mode == 'AUDIO_SYNC' and context.preferences.system.audio_device == 'JACK':
                row.scale_x = 2
                row.operator("screen.animation_play", text="", icon='PLAY')
                row.scale_x = 1
            else:
                row.operator("screen.animation_play", text="", icon='PLAY_REVERSE').reverse = True
                row.operator("screen.animation_play", text="", icon='PLAY')
        else:
            row.scale_x = 2
            row.operator("screen.animation_play", text="", icon='PAUSE')
            row.scale_x = 1
        row.operator("screen.keyframe_jump", text="", icon='NEXT_KEYFRAME').next = True
        row.operator("screen.frame_jump", text="", icon='FF').end = True
       
        

####SHADER######

class NODE_MT_editor_menus(Menu):
    bl_idname = "NODE_MT_editor_menus"
    bl_label = ""

    def draw(self, _context):
        layout = self.layout
        layout.menu("NODE_MT_view")
        layout.menu("NODE_MT_select")
        layout.menu("NODE_MT_add")
        layout.menu("NODE_MT_node")
        
        layout.separator(factor=0.4)
        layout.operator("screen.switch_area_type", icon="NODE_MATERIAL")
        
        layout.separator(factor=0.4)
        layout.operator("screen.switch_area_type_time", icon="TIME")
        
        layout.separator(factor=0.4)
        layout.operator("screen.switch_area_type_graph", icon="GRAPH")
        
        
        
######################################################  operators  ################################################   

class Add_Empty_At_Select_loc(Operator):
    bl_idname = "object.add_empty_at_loc"
    bl_label = "Add Empty to Selected"
    
    def execute(self, context):
        
        cursor_loc = bpy.context.scene.cursor.location
        cursor_loc = mathutils.Vector(cursor_loc)
        
        bpy.ops.view3d.snap_cursor_to_selected()
        
        bpy.ops.object.mode_set(mode='OBJECT')

        bpy.ops.object.empty_add(type='PLAIN_AXES')
        
        bpy.context.scene.cursor.location = cursor_loc
            

        return{'FINISHED'}
    
class Set_Origin_To_sel(Operator):
    bl_idname = "object.set_origin_to_selected"
    bl_label = "Set Origin to Selected"

    def execute(self, context):
        
        cursor_loc = bpy.context.scene.cursor.location
        cursor_loc = mathutils.Vector(cursor_loc)
        
        bpy.ops.view3d.snap_cursor_to_selected()
        
        bpy.ops.object.mode_set(mode='OBJECT')
        
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='BOUNDS')
        
        bpy.context.scene.cursor.location = cursor_loc
        
        return{'FINISHED'}
    

class Snap_ToGround(Operator):
    bl_idname = "object.snap_toground"
    bl_label = "Drop to Ground"
    
#    @classmethod
#    def poll(cls, context: bpy.types.Context):
#        return context.mode == 'OBJECT' and len(context.selected_objects) > 0
    
    def execute(self, context):
        for obj in context.selected_objects:
            mx = obj.matrix_world
            minz = min((mx @ v.co)[2] for v in obj.data.vertices)
            mx.translation.z -= minz
            
        return{'FINISHED'}
    
    
#telemetry = polib.get_telemetry("botaniq")
#telemetry.report_addon(bl_info, __file__)
   
   
   
class Snap_ToGround_Surface(Operator):
    bl_idname = "object.snap_toground_surface"
    bl_label = "Drop to Surface"
    bl_description = "Drop selected assets to the ground, as close as possible."

    bl_options = {'REGISTER', 'UNDO'}

#    @classmethod
#    def poll(cls, context: bpy.types.Context):
#        return context.mode == 'OBJECT' and len(context.selected_objects) > 0

    def execute(self, context):
        
        # We have no way to know which objects are part of ground so we raycast all of them except
        # what's selected. The objects that the user wants to snap to ground are the selected objects.
        # Since we are going to be moving all of those we can't do self-collisions.

        ground_objects = [obj for obj in context.visible_objects if obj.type ==
                          "MESH" and obj not in context.selected_objects]
        selected_objects_names = []
        for obj in context.selected_objects:
            if obj.instance_type == "NONE":
                polib.snap_to_ground.snap_to_ground_no_rotation(
                    obj, obj, ground_objects, telemetry)
            elif obj.instance_type == "COLLECTION":
                collection = obj.instance_collection
                if len(collection.objects) >= 1:
                    polib.snap_to_ground.snap_to_ground_no_rotation(
                        obj, collection.objects[0], ground_objects, telemetry)
            else:
                continue

            selected_objects_names.append(obj.name)

        return {'FINISHED'}





#####################################################   draw   ###################################################    

operators_object = ["object.add_empty_at_loc", "object.snap_toground", "object.snap_toground_surface"]

operators_edit = ["object.add_empty_at_loc", "object.set_origin_to_selected"]
      

class Quick_Addons(bpy.types.Menu):
    bl_label = "Quick Addons"
    bl_idname = "object.my_quick_addons"

    def draw(self, context):
        layout = self.layout
        if context.mode == "OBJECT":
            for oo in operators_object:
                layout.operator(oo)
        elif context.mode == "EDIT_MESH":
            for oe in operators_edit:
                layout.operator(oe)
        
        
class VIEW3D_MT_PIE_MENU(Menu):
    # label is displayed at the center of the pie menu.
    bl_label = "Quick Addons"
    
    def draw(self, context):
        layout = self.layout

        pie = layout.menu_pie()
        # operator_enum will just spread all available options
        # for the type enum of the operator on the pie
        
        if context.mode == "OBJECT":
            for oo in operators_object:
                pie.operator(oo)
        elif context.mode == "EDIT_MESH":
            for oe in operators_edit:
                pie.operator(oe)
        
#    keyconfig = bpy.context.window_manager.keyconfigs.addon
#    keymap = keyconfig.keymaps.new(name="3D View Generic", space_type='VIEW_3D', region_type='WINDOW')  
#    keymap_item = keymap.keymap_items.new("pie.shader",'Q', 'PRESS') 
#    keymap_item.shift = True                         
    #keymap_item.any = True
    #keymap_item.active = True

def draw_item(self, context):
    layout = self.layout
    layout.menu(Quick_Addons.bl_idname)
    

class DrawPie(Operator):
    bl_label = "Quick Addons"
    bl_idname = "pie.caller"
    def execute(self, context):
        bpy.ops.wm.call_menu_pie(name="VIEW3D_MT_PIE_MENU")
        return{'FINISHED'}
    
    
    
##### ADD MAN ######

class OBJECT_OT_add_Man(Operator):
    """Create a new Mesh Object"""
    bl_idname = "mesh.add_man"
    bl_label = "Add Reference Man"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.mode == "EDIT_MESH":
            bpy.ops.object.editmode_toggle()

        bpy.ops.object.select_all(action='DESELECT')

        addon_file = Speedups.__file__
        addon_folder = addon_file.replace("\\__init__.py", "")
        addon_folder = addon_folder.replace("\\", "\\")
        print(addon_folder)
   
        blendfile = addon_folder + "\\CCO_Male_base_mesh_standing.blend"
        section   = "\\Object\\"
        object    = "Man"
        print(blendfile)

        filepath  = blendfile + section + object
        directory = blendfile + section
        filename  = object

        bpy.ops.wm.append(
            filepath=filepath, 
            filename=filename,
            directory=directory)

        bpy.ops.view3d.snap_selected_to_cursor(use_offset=False)

        return {'FINISHED'}


# Registration

def add_Man_button(self, context):
    self.layout.operator(
        OBJECT_OT_add_Man.bl_idname,
        icon='CON_ARMATURE')

classes = (
    TIME_MT_editor_menus,
    Switch_To_OT_ShaderNodeTree,
    Switch_To_OT_GRAPH_EDITOR,
    Switch_To_OT_TIMELINE,
    GRAPH_MT_editor_menus,
    NODE_MT_editor_menus,
    
    Preferences,
    
    Add_Empty_At_Select_loc,
    Set_Origin_To_sel,
    Snap_ToGround,
    Snap_ToGround_Surface,
    
    Quick_Addons,
    DrawPie,
    VIEW3D_MT_PIE_MENU,
    
    OBJECT_OT_add_Man,
)

def register():
    for cls in classes:
        addon_updater_ops.make_annotations(cls)
        bpy.utils.register_class(cls)
    
#    if context.mode == "OBJECT":
    bpy.types.VIEW3D_MT_object.append(draw_item)
#    else:
    bpy.types.VIEW3D_MT_edit_mesh.append(draw_item)
    bpy.types.VIEW3D_MT_mesh_add.append(add_Man_button)
    
    wm = bpy.context.window_manager
    if wm.keyconfigs.addon:
            keyconfig = bpy.context.window_manager.keyconfigs.addon
            km = keyconfig.keymaps.new(name="3D View Generic", space_type='VIEW_3D', region_type='WINDOW')  
            kmi = km.keymap_items.new("pie.caller",'Q', 'PRESS') 
            kmi.shift = True 
            #addon_keymaps.append((km, kmi))
            
            
    
    addon_updater_ops.register(bl_info)
            
def unregister():    
    for cls in classes:
        bpy.utils.unregister_class(cls)
        
#    if context.mode == "OBJECT":
    bpy.types.VIEW3D_MT_object.remove(draw_item)
#    else:
    bpy.types.VIEW3D_MT_edit_mesh.remove(draw_item)
    bpy.types.VIEW3D_MT_mesh_add.remove(add_Man_button)
    
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        for km, kmi in addon_keymaps:
            km.keymap_items.remove(kmi)
    #addon_keymaps.clear()

if __name__ == "__main__":
    register()
    
#print(bpy.context.mode)