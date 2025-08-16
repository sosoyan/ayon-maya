import os

from ayon_core.pipeline import publish
from ayon_core.lib import BoolDef, TextDef, UILabelDef, UISeparatorDef
from ayon_maya.api import plugin

import mgear.pymaya as pm

from mgear.shifter.game_tools_fbx import utils,partition_thread

from maya import cmds


class ExtractMgearGame(plugin.MayaExtractorPlugin,
                       publish.OptionalPyblishPluginMixin):
    """Extractor for Mgear.
    """

    enabled = False
    label = "Extract mGear"
    
    def __init__(self):
        super().__init__()

        self.ext_dict = {
            "up_axis": "Y",
            "file_type": "Binary",
            "fbx_version": "FBX 2020",
            "remove_namespace": True,
            "scene_clean": True,
            "use_partitions": False,
            "cull_joints": False,
            "ue_enabled": False,
            "ue_file_path": "",
            "ue_active_skeleton": ""
        }
    
    @classmethod
    def register_create_context_callbacks(cls, create_context):
        create_context.add_value_changed_callback(cls.on_values_changed)

    @classmethod
    def on_values_changed(cls, event):
        """Update instance attribute definitions on attribute changes.
        """
        for instance_change in event["changes"]:
            # First check if there"s a change we want to respond to
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
    
    @classmethod
    def get_additional_attr_defs(cls, visible):
        return []

class ExtractMgearSkeletalMesh(ExtractMgearGame):
    """Extractor for Mgear Skeletal Mesh
    """

    label = "Extract mGear Game Skeletal Mesh"
    families = ["rig"]

    # Exposed in settings
    optional = True
    active = True
    enabled = True

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
        
        return attr_defs

    def process(self, instance):
        attr_values = self.get_attr_values_from_data(instance.data)

        if attr_values:
           
            if self.is_active(instance.data):
                
                geo_roots = utils.get_geo_root()
                jnt_roots =  utils.get_joint_root()

                if geo_roots and jnt_roots:

                    asset = instance.data("anatomyData").get("asset")
                    product = instance.data("productName")
                    version = instance.data("version")
                    extension = "fbx"
                    
                    self.ext_dict["export_tab"] =  0
                    self.ext_dict["geo_roots"] = geo_roots
                    self.ext_dict["joint_root"] = jnt_roots[0].name()
                    self.ext_dict["file_path"] = instance.data("stagingDir").replace("\\", "/")
                    self.ext_dict["file_name"] = f"{asset}_{product}_v{version:03}.{extension}"
                    
                    self.ext_dict["skinning"] = attr_values["skinning"]
                    self.ext_dict["blendshapes"] = attr_values["blendshapes"]

                    self.log.debug(f"mGear export data - {self.ext_dict}")

                    pt = partition_thread.PartitionThread(self.ext_dict)
                    pt.init_data()
                    pt.start()
                    pt.wait()
                    
                    representation = {
                        "name": extension,
                        "ext": extension,
                        "files": self.ext_dict["file_name"],
                        "stagingDir": self.ext_dict["file_path"]
                    }
                    
                    instance.data["representations"].append(representation)

class ExtractMgearAnimation(ExtractMgearGame):
    """Extractor for Mgear Animation
    """

    label = "Extract mGear Game Animation"
    families = ["animation"]

    # Exposed in settings
    optional = True
    active = True
    enabled = True
    
    def process(self, instance):
        attr_values = self.get_attr_values_from_data(instance.data)

        if attr_values:
           
            if self.is_active(instance.data):
                jnt_roots =  utils.get_joint_root()
                asset = instance.data("anatomyData").get("asset")
                product = instance.data("productName")
                version = instance.data("version")
                frame_start = instance.data("frameStart")
                frame_end = instance.data("frameEnd")
                fps = instance.data("taskEntity").get("attrib").get("fps")

                self.ext_dict["export_tab"] =  1
                self.ext_dict["joint_root"] = jnt_roots[0].name()
                self.ext_dict["file_path"] = instance.data("stagingDir").replace("\\", "/")
                self.ext_dict["file_name"] = f"{asset}_{product}_v{version:03}"
                
                self.log.debug(f"mGear export data - {self.ext_dict}")
                
                current_scene_path = cmds.file(query=True, sceneName=True)
                master_path = os.path.join(self.ext_dict["file_path"], f"{asset}_{product}_v{version:03}.ma")

                cmds.file(rename=master_path)
                ma_file = cmds.file(type="mayaAscii", force=True, pr=False, exportAll=True)

                cmds.file(ma_file, open=True, force=True, save=False)

                cmds.parent(self.ext_dict["joint_root"], world=True)
                
                clip_data = {"title": product,
                             "enabled": True,
                             "frame_rate": fps,
                             "start_frame": frame_start,
                             "end_frame": frame_end}
                
                fbx_file_path = utils.export_animation_clip(self.ext_dict, clip_data)
                
                cmds.file(current_scene_path, open=True, force=True, save=False)
                cmds.file(modified=False)

                ma_repr = {
                        "name": "ma",
                        "ext": "ma",
                        "files": os.path.basename(ma_file),
                        "stagingDir": self.ext_dict["file_path"]
                    }

                fbx_repr = {
                        "name": "fbx",
                        "ext": "fbx",
                        "files": os.path.basename(fbx_file_path),
                        "stagingDir": self.ext_dict["file_path"]
                    }
                
                instance.data["representations"].append(ma_repr)
                instance.data["representations"].append(fbx_repr)


