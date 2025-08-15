import contextlib
import json
import os

from ayon_core.pipeline import publish
from ayon_core.lib import BoolDef, EnumDef, UILabelDef, UISeparatorDef
from ayon_maya.api.lib import maintained_selection, maintained_time
from ayon_maya.api import plugin

import mgear.pymaya as pm

from mgear.shifter.game_tools_fbx import (
    anim_clip_widgets,
    fbx_export_node,
    partitions_outliner,
    utils,
    partition_thread
)

from maya import cmds
import maya.api.OpenMaya as om

class ExtractMgearGame(plugin.MayaExtractorPlugin,
                       publish.OptionalPyblishPluginMixin):
    """Extractor for Mgear.
    """

    enabled = True
    label = "Extract Mgear"

    def filter_members(self, members):
        print("filter_members", members)
        return members
    
    @classmethod
    def register_create_context_callbacks(cls, create_context):
        create_context.add_value_changed_callback(cls.on_values_changed)

    @classmethod
    def on_values_changed(cls, event):
        """Update instance attribute definitions on attribute changes."""
        for instance_change in event["changes"]:
            # First check if there's a change we want to respond to
            instance = instance_change["instance"]
            if instance is None:
                # Change is on context
                continue

            # Check if active state is toggled
            value_changes = instance_change["changes"]
            if "publish_attributes" not in value_changes:
                continue

            publish_attributes = value_changes["publish_attributes"]
            class_name = cls.__name__
            if class_name not in publish_attributes:
                continue

            if "active" not in publish_attributes[class_name]:
                continue

            # Update the attribute definitions
            new_attrs = cls.get_attr_defs_for_instance(
                event["create_context"], instance
            )
            instance.set_publish_plugin_attr_defs(class_name, new_attrs)

    @classmethod
    def get_attr_defs_for_instance(cls, create_context, instance):

        is_enabled = cls.enabled
        
        if not is_enabled:
            return []

        if not cls.instance_matches_plugin_families(instance):
            return []

        if cls.optional:
            plugin_attr_values = (
                instance.data
                .get("publish_attributes", {})
                .get(cls.__name__, {})
            )
            is_enabled = plugin_attr_values.get("active", cls.active)
        
        attr_defs = []
        extract_mgear_opt = super().get_attr_defs_for_instance(create_context,
                                                               instance)
        
        if extract_mgear_opt:
            attr_defs.extend(extract_mgear_opt)

            attr_defs.extend([
                UISeparatorDef("sep_mgear_options", visible=is_enabled),
                UILabelDef("mGear Options", visible=is_enabled),
            ])
            
            attr_defs.extend(cls.get_additional_attr_defs(is_enabled))
            
            attr_defs.append(
                UISeparatorDef("sep_mgear_options_end")
            )

        return attr_defs
    
    def get_additional_attr_defs(cls, visible):
        pass

class ExtractMgearSkeletalMesh(ExtractMgearGame):
    """Extractor for Mgear Skeletal Mesh
    """

    label = "Extract mGear Game Skeletal Mesh"
    families = ["rig"]

    # Exposed in settings
    optional = True
    active = True
    
    @classmethod
    def get_additional_attr_defs(cls, is_enabled):
        attr_defs = []
        attr_defs.append(BoolDef("skinning",
            label="Skinning",
            tooltip="",
            visible=is_enabled,
            default=True))
        attr_defs.append(BoolDef("blendshapes",
                label="Blendshapes",
                tooltip="",
                visible=is_enabled,
                default=True))
        attr_defs.append(BoolDef("partitions",
                label="Partitions",
                tooltip="",
                visible=is_enabled,
                default=True))
        attr_defs.append(BoolDef("cullJoints",
            label="Cull Joints",
            tooltip="",
            visible=is_enabled,
            default=False))
        
        return attr_defs

    def process(self, instance):
        attr_values = self.get_attr_values_from_data(instance.data)

        if attr_values:
            print("HEllo I'm Mgear Skeletal Mesh extractor")
           
            if self.is_active(instance.data):
                members = instance.data("setMembers")
                jnt_root = utils.get_joint_root()
                geo_root = utils.get_geo_root()
                
                rig_geo_roots_grp_set = pm.ls("rig_geo_roots_grp", type="objectSet")
                geo_roots = pm.sets(rig_geo_roots_grp_set, q=True, nodesOnly=False)
                publish_dir = instance.data("publishDir")

                #geo_root_set = next((i for i in members if i == "mgear_geo_roots"), utils.get_geo_root())
                #geo_roots = pm.sets(geo_root_set, q=True, nodesOnly=False)
                #geo_root = utils.get_geo_root()
                    
                            
        print(STOP)

class ExtractMgearAnimation(ExtractMgearGame):
    """Extractor for Mgear Animation
    """

    label = "Extract mGear Game Animation"
    families = ["animation"]

    # Exposed in settings
    optional = True
    active = True

    def process(self, instance):
        print("HEllo I'm Mgear Anim extractor")


