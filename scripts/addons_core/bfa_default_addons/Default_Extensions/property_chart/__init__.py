# SPDX-FileCopyrightText: 2010-2022 Blender Foundation
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""List properties of selected objects"""

import bpy
from bl_operators.presets import AddPresetBase
from bpy.types import (
    Menu,
    Operator,
    Panel,
)


class AddPresetProperties(AddPresetBase, Operator):
    """Add an properties preset"""
    bl_idname = "scene.properties_preset_add"
    bl_label = "Add Properties Preset"
    preset_menu = "SCENE_MT_properties_presets"

    preset_defines = [
        "scene = bpy.context.scene",
    ]

    def pre_cb(self, context):
        space_type = context.space_data.type
        if space_type == 'VIEW_3D':
            self.preset_subdir = "system_property_chart_view3d"
            self.preset_values = ["scene.view3d_edit_props"]
        else:
            self.preset_subdir = "system_property_chart_sequencer"
            self.preset_values = ["scene.sequencer_edit_props"]


class SCENE_MT_properties_presets(Menu):
    bl_label = "Properties Presets"
    preset_operator = "script.execute_preset"

    def draw(self, context):
        space_type = context.space_data.type

        if space_type == 'VIEW_3D':
            self.preset_subdir = "system_property_chart_view3d"
        else:
            self.preset_subdir = "system_property_chart_sequencer"

        Menu.draw_preset(self, context)


def _property_chart_data_get(self, context):
    # eg. context.active_object
    obj = eval("context.%s" % self.context_data_path_active)

    if obj is None:
        return None, None

    # eg. context.selected_objects[:]
    selected_objects = eval("context.%s" % self.context_data_path_selected)[:]

    if not selected_objects:
        return None, None

    return obj, selected_objects


def _property_chart_draw(self, context):
    """
    This function can run for different types.
    """
    obj, selected_objects = _property_chart_data_get(self, context)

    if not obj:
        return

    # active first
    try:
        active_index = selected_objects.index(obj)
    except ValueError:
        active_index = -1

    if active_index > 0:  # not the first already
        selected_objects[0], selected_objects[active_index] = selected_objects[active_index], selected_objects[0]

    id_storage = context.scene

    strings = getattr(id_storage, self._PROP_STORAGE_ID)

    # Collected all props, now display them all
    layout = self.layout

    if strings:

        def obj_prop_get(obj, attr_string):
            """return a pair (rna_base, "rna_property") to give to the rna UI property function"""
            attrs = attr_string.split(".")
            val_new = obj
            for i, attr in enumerate(attrs):
                val_old = val_new
                val_new = getattr(val_old, attr, Ellipsis)

                if val_new == Ellipsis:
                    return None, None
            return val_old, attrs[-1]

        strings = strings.split()

        prop_all = []

        for obj in selected_objects:
            prop_pairs = []
            prop_found = False
            for attr_string in strings:
                prop_pairs.append(obj_prop_get(obj, attr_string))
                if prop_found is False and prop_pairs[-1] != (None, None):
                    prop_found = True

            if prop_found:
                prop_all.append((obj, prop_pairs))

        row = layout.row(align=True)

        col = row.column(align=True)
        col.label(text="name")
        for obj, prop_pairs in prop_all:
            col.prop(obj, "name", text="")

        for i in range(len(strings)):
            col = row.column(align=True)

            # name and copy button
            rowsub = col.row(align=False)
            rowsub.label(text=strings[i].rsplit(".", 1)[-1])
            props = rowsub.operator("wm.chart_copy", text="", icon='PASTEDOWN', emboss=False)
            props.data_path_active = self.context_data_path_active
            props.data_path_selected = self.context_data_path_selected
            props.data_path = strings[i]

            for obj, prop_pairs in prop_all:
                data, attr = prop_pairs[i]
                # row is needed for vector buttons
                if data:
                    col.row().prop(data, attr, text="")  # , emboss=obj==active_object
                else:
                    col.label(text="<missing>")

    # Presets for properties
    col = layout.column()
    col.label(text="Properties")
    row = col.row(align=True)
    row.menu("SCENE_MT_properties_presets", text=bpy.types.SCENE_MT_properties_presets.bl_label)
    row.operator("scene.properties_preset_add", text="", icon='ADD')
    row.operator("scene.properties_preset_add", text="", icon='REMOVE').remove_active = True
    # edit the display props
    col.prop(id_storage, self._PROP_STORAGE_ID, text="")


class View3DEditProps(Panel):
    bl_idname = "SYSPROP_CHART_PT_view3d"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Item"
    bl_label = "Property Chart"
    bl_context = "objectmode"
    bl_options = {'DEFAULT_CLOSED'}

    _PROP_STORAGE_ID = "view3d_edit_props"
    _PROP_STORAGE_ID_DESCR = "Properties of objects in the context"
    _PROP_STORAGE_DEFAULT = "data show_wire"

    # _property_chart_draw needs these
    context_data_path_active = "active_object"
    context_data_path_selected = "selected_objects"

    draw = _property_chart_draw


class SequencerEditProps(Panel):
    bl_idname = "SYSPROP_CHART_PT_sequencer"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Item"
    bl_label = "Property Chart"
    bl_options = {'DEFAULT_CLOSED'}

    _PROP_STORAGE_ID = "sequencer_edit_props"
    _PROP_STORAGE_ID_DESCR = "Properties of sequencer strips in the context"
    _PROP_STORAGE_DEFAULT = "blend_type blend_alpha"

    # _property_chart_draw needs these
    context_data_path_active = "scene.sequence_editor.active_strip"
    context_data_path_selected = "selected_sequences"

    draw = _property_chart_draw

    @classmethod
    def poll(cls, context):
        return context.scene.sequence_editor is not None

# Operator to copy properties


def _property_chart_copy(self, context):
    obj, selected_objects = _property_chart_data_get(self, context)

    if not obj:
        return

    data_path = self.data_path

    data_path_with_dot = data_path
    if not data_path_with_dot.startswith("["):
        data_path_with_dot = "." + data_path_with_dot

    code = compile(
        "obj_iter%s = obj%s" % (data_path_with_dot, data_path_with_dot),
        "<property_chart>",
        'exec',
    )

    for obj_iter in selected_objects:
        if obj != obj_iter:
            try:
                exec(code, {}, {"obj": obj, "obj_iter": obj_iter})
            except:
                # just in case we need to know what went wrong!
                import traceback
                traceback.print_exc()


from bpy.props import StringProperty


class CopyPropertyChart(Operator):
    "Open a path in a file browser"
    bl_idname = "wm.chart_copy"
    bl_label = "Copy properties from active to selected"

    data_path_active: StringProperty()
    data_path_selected: StringProperty()
    data_path: StringProperty()

    def execute(self, context):
        # so attributes are found for '_property_chart_data_get()'
        self.context_data_path_active = self.data_path_active
        self.context_data_path_selected = self.data_path_selected

        _property_chart_copy(self, context)

        return {'FINISHED'}

# List The Classes #


classes = (
    AddPresetProperties,
    SCENE_MT_properties_presets,
    View3DEditProps,
    SequencerEditProps,
    CopyPropertyChart
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    Scene = bpy.types.Scene

    for cls in View3DEditProps, SequencerEditProps:
        setattr(
            Scene,
            cls._PROP_STORAGE_ID,
            StringProperty(
                name="Properties",
                description=cls._PROP_STORAGE_ID_DESCR + " (separated by spaces)",
                default=cls._PROP_STORAGE_DEFAULT, maxlen=1024,
            ),
        )


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    Scene = bpy.types.Scene

    for cls in View3DEditProps, SequencerEditProps:
        delattr(Scene,
                cls._PROP_STORAGE_ID,
                )


if __name__ == "__main__":
    register()
