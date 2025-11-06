import os
import json

from pathlib import Path
import maya.cmds as cmds
import maya.api.OpenMaya as om


from ayon_maya.api import plugin
from ayon_core.pipeline import get_current_folder_path


def get_obj_quaternion(obj):
    selection = om.MGlobal.getSelectionListByName(obj)
    dagPath = selection.getDagPath(0)
    world_matrix = dagPath.inclusiveMatrix()
    transform = om.MTransformationMatrix(world_matrix)

    return transform.rotation(asQuaternion=True)

class ExtractAssemblyJson(plugin.MayaExtractorPlugin):
    """Extract Assembly JSON

    """
    label = "Extract Assembly (JSON)"
    families = ["layout"]
    
    def process(self, instance):
        staging_dir = self.staging_dir(instance)
        json_filename = f"{instance.name}.json"
        json_path = os.path.join(staging_dir, json_filename)
        members = [member.lstrip('|') for member in instance.data["setMembers"]]

        objects_data = []    
        for obj in members:
            child = cmds.listRelatives(obj, children=True, fullPath=False)
            parent = cmds.listRelatives(obj,  parent=True, fullPath=True)
            
            object_name = cmds.ls(obj, shortNames=True)[0]
            object_path = parent[0] if parent else "|"

            if child:
                ref_path_parts = Path(cmds.referenceQuery(child[0], filename=True)).parts
                asset_type = ref_path_parts[3]
                asset_name = ref_path_parts[4]
                product_name = ref_path_parts[8]
                translation = cmds.xform(obj, query=True, translation=True, worldSpace=True)
                rotation = get_obj_quaternion(obj)
                scale = cmds.xform(obj, query=True, scale=True, worldSpace=True)
                
                transform_data = {
                    "asset_type": asset_type,
                    "asset_name": asset_name,
                    "product_name": product_name,
                    "object_name": object_name,
                    "object_path": object_path,
                    "translation": translation,
                    "rotation": [rotation.x, rotation.y, rotation.z, rotation.w],
                    "scale": scale,
                }
                objects_data.append(transform_data)
            else:
                cmds.warning(f"Object {obj} does not have a child reference, skipping!")

        assembly_name = Path(get_current_folder_path()).name

        extracted_data = {
            "version": "1.0",
            "name": assembly_name,
            "type": "assembly",
            "objects": objects_data
        }
        
        try:
            with open(json_path, "w") as outfile:
                json.dump(extracted_data, outfile, indent=4)

            self.log.info(f"Transform data extracted: {extracted_data}")
        except Exception as e:
            cmds.warning(f"Failed to write file: {e}")
