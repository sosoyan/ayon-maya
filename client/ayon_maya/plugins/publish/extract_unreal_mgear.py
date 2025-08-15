import contextlib
import json
import os

from ayon_core.pipeline import publish
from ayon_core.lib import BoolDef, EnumDef, UILabelDef, UISeparatorDef
from ayon_maya.api.lib import maintained_selection, maintained_time
from ayon_maya.api import plugin

from maya import cmds
import maya.api.OpenMaya as om


class ExtractMgear(plugin.MayaExtractorPlugin,
                   publish.OptionalPyblishPluginMixin):
    """Extractor for Mgear.
    """

    enabled = True
    label = "Extract Mgear"
    families = ["rig", "animation"]


    def filter_members(self, members):
        print("filter_members", members)
        return members

    def process(self, instance):
        print("HEllo I'm Mgear abstract extractor")
    
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

        extract_mgear_opt = super().get_attr_defs_for_instance(create_context,
                                                               instance)
        
        if extract_mgear_opt:
            attr_defs = extract_mgear_opt
        
            attr_defs.extend([
                UISeparatorDef("sep_mgear_options", visible=is_enabled),
                UILabelDef("mGear Options", visible=is_enabled),
            ])

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
            
            attr_defs.append(
                UISeparatorDef("sep_mgear_options_end")
            )

        return attr_defs

class ExtractMgearRig(ExtractMgear):
    """Extractor for Mgear Rig
    """

    label = "Extract mGear Rig"
    families = ["rig"]

    # Exposed in settings
    optional = True
    active = True

    def process(self, instance):
        print("HEllo I'm Mgear Rig extractor")

class ExtractMgearAnim(ExtractMgear):
    """Extractor for Mgear Animation
    """

    label = "Extract mGear Animation"
    families = ["animation"]

    # Exposed in settings
    optional = True
    active = True

    def process(self, instance):
        print("HEllo I'm Mgear Anim extractor")


