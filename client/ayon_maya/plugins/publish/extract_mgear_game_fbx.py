import os
import pyblish.api
from ayon_core.pipeline import publish
from ayon_core.lib import EnumDef, BoolDef, UILabelDef, UISeparatorDef
from ayon_maya.api import plugin

try:
    from mgear.core import pyFBX
    from mgear.shifter.game_tools_fbx import utils, partition_thread
    MGEAR_INSTALLED = True
except ImportError:
    MGEAR_INSTALLED = False

from maya import cmds


def get_all_children(obj):

    children = cmds.listRelatives(obj, children=True, fullPath=True) or []
    all_nodes = []
    for child in children:
        all_nodes.append(child)
        all_nodes.extend(get_all_children(child))
    return all_nodes

def find_blendshape_nodes(root):
    """
    Return list of objects under root that have blendshapes.
    """
    result = []
    
    all_nodes = get_all_children(root)
    for node in all_nodes:
        
        shapes = cmds.listRelatives(node, shapes=True, fullPath=True) or []
        for shape in shapes:
            history = cmds.listHistory(shape) or []
            for h in history:
                if cmds.nodeType(h) == "blendShape":
                    result.append(node)
                    break
    return list(set(result))

def get_blendshape_attrs(obj):

    if not cmds.objExists(obj):
        raise RuntimeError("Object '{}' does not exist.".format(obj))

    shapes = cmds.listRelatives(obj, shapes=True, ni=True, fullPath=True) or []
    if not shapes:
        return []

    bs_nodes = set()
    for s in shapes:
        hist = cmds.listHistory(s, pruneDagObjects=True) or []
        for h in hist:
            if cmds.nodeType(h) == "blendShape":
                bs_nodes.add(h)

    if not bs_nodes:
        return []

    attrs = []
    for bs in bs_nodes:
        alias_list = cmds.aliasAttr(bs, q=True) or []
        plug_to_alias = {}
        for i in range(0, len(alias_list), 2):
            alias_name = alias_list[i]
            real_attr  = alias_list[i+1]
            plug_to_alias[real_attr] = alias_name

        indices = cmds.getAttr(bs + ".weight", multiIndices=True) or []
        for idx in indices:
            plug = "{}.weight[{}]".format(bs, idx)
            alias = plug_to_alias.get("weight[{}]".format(idx))
            attrs.append("{}.{}".format(bs, alias) if alias else plug)

    return attrs

class LocalRefs:
    def __init__(self, use_partitions, stage_dir, geo_roots):
        self.use_partitions = use_partitions
        self.stage_dir = stage_dir
        self.geo_roots = geo_roots
        self.scene_path = ""
        self.tmp_scene_path = ""
        self.is_referenced = False

    def __enter__(self):
        
        if self.use_partitions:

            self.is_referenced = any(cmds.referenceQuery(
                obj, isNodeReferenced=True) for obj in self.geo_roots)
            
            if self.is_referenced:

                self.scene_path = cmds.file(query=True, sceneName=True)
                self.tmp_scene_path = os.path.join(self.stage_dir, os.path.basename(self.scene_path))
                cmds.file(save=True)
                
                cmds.file(rename=self.tmp_scene_path)
                ma_file = cmds.file(type="mayaAscii", force=True, pr=False, exportAll=True)

                cmds.file(ma_file, open=True, force=True, save=False)

        return True

    def __exit__(self, exc_type, exc_value, traceback):
        if self.is_referenced:
            cmds.file(self.scene_path, open=True, force=True, save=False)
            cmds.file(modified=False)
            
            try:
                os.remove(self.tmp_scene_path)
            except FileNotFoundError:
                pass

        return False

class ExtractMgearGame(plugin.MayaExtractorPlugin,
                       publish.OptionalPyblishPluginMixin):
    """Extractor for Mgear.
    """
    order = pyblish.api.ExtractorOrder + 0.1

    enabled = False
    label = "Extract mGear"
    
    def __init__(self):
        super().__init__()

        self.exp_config = {
            "up_axis": "Y",
            "file_type": "Binary",
            "fbx_version": "FBX 2020",
            "remove_namespace": True,
            "scene_clean": True,
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
    enabled = MGEAR_INSTALLED

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
        
        attr_defs.append(BoolDef("use_partitions",
                label="Use Partitions",
                tooltip="",
                visible=is_enabled,
                default=True))
        
        attr_defs.append(BoolDef("cull_joints",
                label="Cull Joints",
                tooltip="",
                visible=is_enabled,
                default=False))

        fbx_presets_list = pyFBX.get_fbx_export_presets()
        
        if fbx_presets_list:
            
            enum_items = {
                path: os.path.splitext(os.path.basename(path))[0]
                for path in fbx_presets_list
            }
            
            attr_defs.append(EnumDef("fbx_preset",
                        label="Fbx Preset",
                        items=enum_items,
                        visible=is_enabled,
                        default=fbx_presets_list[-1]))

        return attr_defs

    def process(self, instance):
        attr_values = self.get_attr_values_from_data(instance.data)

        if attr_values:
           
            if self.is_active(instance.data):
                
                geo_roots = utils.get_geo_root()
                jnt_roots =  utils.get_joint_root()

                if geo_roots and jnt_roots:
                    
                    folder_name = instance.data("anatomyData")["folder"]["name"]
                    product_name = instance.data("productName")
                    version = instance.data("version")
                    padding = instance.data(
                        "projectEntity")['config']['templates']['common']['version_padding']
                    staging_dir = instance.data("stagingDir").replace("\\", "/")
                    extension = "fbx"

                    self.exp_config["export_tab"] =  0
                    self.exp_config["geo_roots"] = geo_roots
                    self.exp_config["joint_root"] = jnt_roots[0].name()
                    self.exp_config["file_path"] = staging_dir
                    self.exp_config["file_name"] = f"{folder_name}_{product_name}"
                    self.exp_config["skinning"] = attr_values["skinning"]
                    self.exp_config["blendshapes"] = attr_values["blendshapes"]
                    self.exp_config["use_partitions"] = attr_values["use_partitions"]
                    self.exp_config["cull_joints"] = attr_values["cull_joints"]
                    self.exp_config["preset_path"] = attr_values["fbx_preset"]

                    representations = []
                    partition_sets = cmds.ls("rig_prt_*", type="objectSet")
                    use_partitions = partition_sets and attr_values["use_partitions"]
                    
                    if use_partitions:
                        self.exp_config["partitions"] = {}

                        for prt_set in partition_sets:
                            prt_geos = cmds.sets(prt_set, q=True)
                            prt_geos_long = [cmds.ls(obj, l=True)[0] for obj in prt_geos]

                            prt_name = prt_set.replace("rig_prt_", "")
                            self.exp_config["partitions"][prt_name] = {
                                    "enabled": True,
                                    "skeletal_meshes": prt_geos_long
                                }
                            
                            representations.append({
                                "name": f"{prt_name}_{extension}",
                                "ext": f"{prt_name}.{extension}",
                                "files": f"{folder_name}_{product_name}_{prt_name}.{extension}",
                                "stagingDir": staging_dir
                            })
                    else:
                        representations.append({
                                "name": extension,
                                "ext": extension,
                                "files": f"{folder_name}_{product_name}.{extension}",
                                "stagingDir": staging_dir
                            })
                    
                    self.log.debug(f"mGear export config - {self.exp_config}")
                    
                    with LocalRefs(use_partitions, staging_dir, geo_roots):                    
                        pt = partition_thread.PartitionThread(self.exp_config)
                        pt.init_data()
                        pt.start()
                        pt.wait()

                    for rep in representations:
                        fn = rep["files"]
                        name, ext = os.path.splitext(fn)
                        new_fn = f"{name}_v{version:0{padding}d}{ext}"
                        
                        os.rename(os.path.join(staging_dir, fn), 
                                  os.path.join(staging_dir, new_fn))
                        
                        rep["files"] = new_fn
                    
                    instance.data["representations"].extend(representations)

class ExtractMgearAnimation(ExtractMgearGame):
    """Extractor for Mgear Animation
    """

    label = "Extract mGear Game Animation"
    families = ["animation"]

    # Exposed in settings
    optional = True
    active = True
    enabled = MGEAR_INSTALLED
    
    def create_blendshape_attrs(self, geo_roots, joint_root):
        for geo in geo_roots:
            for node in find_blendshape_nodes(geo):
                for bs_attr in get_blendshape_attrs(node):
                    attr_name = bs_attr.split(".")[-1]
                    
                    cmds.addAttr(
                        joint_root, 
                        longName=attr_name, 
                        attributeType="float", 
                        defaultValue=0,
                        keyable=True, 
                        minValue=0, 
                        maxValue=1)
                    
                    cmds.connectAttr(bs_attr, f"{joint_root}.{attr_name}")

                    self.log.debug(f"added root blendshape attribute {joint_root}.{attr_name}")

    @classmethod
    def get_additional_attr_defs(cls, is_enabled):
        attr_defs = []
        
        attr_defs.append(BoolDef("blendshapes_anim",
            label="BlendShapes Animation",
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
                    
                    folder_name = instance.data("anatomyData")["folder"]["name"]
                    product_name = instance.data("productName")
                    version = instance.data("version")
                    padding = instance.data(
                        "projectEntity")['config']['templates']['common']['version_padding']
                    frame_start = instance.data("frameStart")
                    frame_end = instance.data("frameEnd")
                    fps = instance.data("taskEntity").get("attrib").get("fps")

                    self.exp_config["export_tab"] =  1
                    self.exp_config["geo_roots"] = geo_roots
                    self.exp_config["joint_root"] = jnt_roots[0].name()
                    self.exp_config["file_path"] = instance.data("stagingDir").replace("\\", "/")
                    self.exp_config["file_name"] = f"{folder_name}_{product_name}_v{version:03}"
                    
                    if attr_values["blendshapes_anim"]:
                        self.create_blendshape_attrs(self.exp_config["geo_roots"], 
                                                     self.exp_config["joint_root"])

                    self.log.debug(f"mGear export data - {self.exp_config}")
                    
                    current_scene_path = cmds.file(query=True, sceneName=True)
                    master_path = os.path.join(
                        self.exp_config["file_path"], 
                        f"{folder_name}_{product_name}_v{version:0{padding}}.ma")

                    cmds.file(rename=master_path)
                    ma_file = cmds.file(type="mayaAscii", force=True, pr=False, exportAll=True)

                    cmds.file(ma_file, open=True, force=True, save=False)

                    cmds.parent(self.exp_config["joint_root"], world=True)
                    
                    clip_data = {"title": product_name,
                                "enabled": True,
                                "frame_rate": fps,
                                "start_frame": frame_start,
                                "end_frame": frame_end}
                    
                    fbx_file_path = utils.export_animation_clip(self.exp_config, clip_data)
                    
                    cmds.file(current_scene_path, open=True, force=True, save=False)
                    cmds.file(modified=False)

                    ma_repr = {
                            "name": "ma",
                            "ext": "ma",
                            "files": os.path.basename(ma_file),
                            "stagingDir": self.exp_config["file_path"]
                        }

                    fbx_repr = {
                            "name": "fbx",
                            "ext": "fbx",
                            "files": os.path.basename(fbx_file_path),
                            "stagingDir": self.exp_config["file_path"]
                        }
                    
                    instance.data["representations"].append(ma_repr)
                    instance.data["representations"].append(fbx_repr)


