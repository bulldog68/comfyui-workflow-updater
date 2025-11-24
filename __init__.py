import json
import os
import folder_paths

class LoadWorkflowFromFile:
    @classmethod
    def INPUT_TYPES(cls):
        input_dir = folder_paths.get_input_directory()
        files = [f for f in os.listdir(input_dir) if f.endswith('.json')]
        return {
            "required": {
                "workflow_file": (files, {"file_upload": True}),
            }
        }
    
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("workflow",)
    FUNCTION = "load_workflow"
    CATEGORY = "utils/workflow"
    DESCRIPTION = "Load workflow from JSON file"

    def load_workflow(self, workflow_file):
        try:
            input_dir = folder_paths.get_input_directory()
            file_path = os.path.join(input_dir, workflow_file)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                workflow_data = json.load(f)
            
            workflow_json = json.dumps(workflow_data)
            return (workflow_json,)
            
        except Exception as e:
            print(f"Error loading workflow file: {e}")
            return ("{}",)

class SaveWorkflowToFile:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "workflow": ("STRING", {"default": "{}", "multiline": True}),
                "filename": ("STRING", {"default": "updated_workflow"}),
            }
        }
    
    RETURN_TYPES = ()
    FUNCTION = "save_workflow"
    OUTPUT_NODE = True
    CATEGORY = "utils/workflow"
    DESCRIPTION = "Save workflow to JSON file"

    def save_workflow(self, workflow, filename):
        try:
            output_dir = folder_paths.get_output_directory()
            
            if not filename.endswith('.json'):
                filename += '.json'
            
            file_path = os.path.join(output_dir, filename)
            
            workflow_data = json.loads(workflow)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(workflow_data, f, indent=2)
            
            print(f"Workflow saved to: {file_path}")
            
        except Exception as e:
            print(f"Error saving workflow: {e}")
        
        return ()

class WorkflowVersionManager:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "workflow": ("STRING", {"default": "{}", "multiline": True}),
                "action": (["analyze", "update"], {"default": "analyze"}),
            },
            "optional": {
                "comfyui_path": ("STRING", {"default": ""}),
            }
        }
    
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("workflow_output", "analysis_report")
    FUNCTION = "process_workflow"
    CATEGORY = "utils/workflow"
    DESCRIPTION = "Analyze and update node versions in workflows"

    def __init__(self):
        pass

    def extract_nodes_from_workflow(self, workflow_data):
        """Extract node types and versions from workflow"""
        nodes_info = {}
        
        def traverse(obj):
            if isinstance(obj, dict):
                if 'type' in obj and obj['type']:
                    node_type = obj['type']
                    version = "N/A"
                    
                    if 'properties' in obj and isinstance(obj['properties'], dict):
                        if 'ver' in obj['properties'] and obj['properties']['ver']:
                            version = str(obj['properties']['ver'])
                        elif 'cnr_id' in obj['properties'] and obj['properties']['cnr_id']:
                            node_type = str(obj['properties']['cnr_id'])
                    
                    if node_type not in nodes_info:
                        nodes_info[node_type] = set()
                    if version:
                        nodes_info[node_type].add(version)
                
                for value in obj.values():
                    traverse(value)
            elif isinstance(obj, list):
                for item in obj:
                    traverse(item)
        
        try:
            traverse(workflow_data)
        except Exception:
            pass
        
        result = {}
        for node_type, versions in nodes_info.items():
            result[node_type] = list(versions)
        
        return result

    def get_installed_nodes_versions(self, comfyui_path=None):
        """Get installed nodes and their versions"""
        if not comfyui_path:
            comfyui_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        installed_nodes = {}
        
        # Get core ComfyUI version
        core_version = self.get_core_version(comfyui_path)
        installed_nodes["comfy-core"] = core_version
        
        # Scan custom nodes directory
        custom_nodes_dir = os.path.join(comfyui_path, "custom_nodes")
        if os.path.exists(custom_nodes_dir):
            try:
                for node_dir in os.listdir(custom_nodes_dir):
                    node_path = os.path.join(custom_nodes_dir, node_dir)
                    if os.path.isdir(node_path) and not node_dir.startswith('.'):
                        version = self.get_node_version(node_path)
                        installed_nodes[node_dir] = version
            except Exception:
                pass
        
        return installed_nodes

    def get_core_version(self, comfyui_path):
        """Get ComfyUI core version"""
        try:
            pyproject_path = os.path.join(comfyui_path, "pyproject.toml")
            if os.path.exists(pyproject_path):
                with open(pyproject_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        if line.strip().startswith('version ='):
                            version = line.split('=', 1)[1].strip().strip('"').strip("'")
                            if version:
                                return version
            
            package_path = os.path.join(comfyui_path, "package.json")
            if os.path.exists(package_path):
                with open(package_path, 'r', encoding='utf-8', errors='ignore') as f:
                    data = json.load(f)
                    return data.get('version', 'Unknown')
                    
        except Exception:
            pass
        
        return "Unknown"

    def get_node_version(self, node_path):
        """Get version from node directory"""
        try:
            init_path = os.path.join(node_path, "__init__.py")
            if os.path.exists(init_path):
                with open(init_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        if line.strip().startswith('__version__'):
                            version = line.split('=', 1)[1].strip().strip('"').strip("'")
                            if version:
                                return version
            
            pyproject_path = os.path.join(node_path, "pyproject.toml")
            if os.path.exists(pyproject_path):
                with open(pyproject_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        if line.strip().startswith('version ='):
                            version = line.split('=', 1)[1].strip().strip('"').strip("'")
                            if version:
                                return version
                                
        except Exception:
            pass
        
        return "Unknown"

    def update_workflow_versions(self, workflow_data, installed_nodes):
        """Update workflow with current versions"""
        
        def update_node(obj):
            if isinstance(obj, dict):
                if 'properties' in obj and isinstance(obj['properties'], dict):
                    if 'cnr_id' in obj['properties'] and obj['properties']['cnr_id']:
                        node_id = str(obj['properties']['cnr_id'])
                        if node_id in installed_nodes and installed_nodes[node_id] not in ["Unknown", "N/A"]:
                            obj['properties']['ver'] = installed_nodes[node_id]
                
                for key in obj:
                    obj[key] = update_node(obj[key])
                return obj
            elif isinstance(obj, list):
                return [update_node(item) for item in obj]
            else:
                return obj
        
        updated_workflow = update_node(workflow_data.copy())
        
        if 'extra' not in updated_workflow:
            updated_workflow['extra'] = {}
        
        filtered_versions = {k: v for k, v in installed_nodes.items() if v != "Unknown"}
        updated_workflow['extra']['node_versions'] = filtered_versions
        
        return updated_workflow

    def process_workflow(self, workflow, action, comfyui_path=""):
        """Main processing function"""
        try:
            if isinstance(workflow, str):
                workflow_data = json.loads(workflow)
            else:
                workflow_data = workflow
            
            actual_comfyui_path = comfyui_path if comfyui_path else None
            
            result = ""
            analysis_report = ""
            
            if action == "analyze":
                workflow_nodes = self.extract_nodes_from_workflow(workflow_data)
                installed_nodes = self.get_installed_nodes_versions(actual_comfyui_path)
                
                analysis_report = "=== Workflow Analysis ===\n"
                analysis_report += f"Nodes found in workflow: {len(workflow_nodes)}\n"
                
                for node_type, versions in workflow_nodes.items():
                    version_str = ', '.join(versions) if versions else "N/A"
                    analysis_report += f"- {node_type}: {version_str}\n"
                
                analysis_report += f"\nInstalled nodes: {len(installed_nodes)}\n"
                for node, version in installed_nodes.items():
                    analysis_report += f"- {node}: {version}\n"
                
                analysis_report += "\n=== Version Check ===\n"
                mismatches = []
                for node_type, versions in workflow_nodes.items():
                    if node_type in installed_nodes:
                        installed_ver = installed_nodes[node_type]
                        if installed_ver not in versions and installed_ver != "Unknown":
                            versions_str = ', '.join(versions) if versions else "N/A"
                            mismatches.append(f"- {node_type}: workflow has [{versions_str}], installed is {installed_ver}")
                
                if mismatches:
                    analysis_report += f"Potential version mismatches found: {len(mismatches)}\n"
                    analysis_report += "\n".join(mismatches)
                else:
                    analysis_report += "No version mismatches detected."
                
                result = json.dumps(workflow_data, indent=2)
                
            elif action == "update":
                installed_nodes = self.get_installed_nodes_versions(actual_comfyui_path)
                updated_workflow = self.update_workflow_versions(workflow_data, installed_nodes)
                
                result = json.dumps(updated_workflow, indent=2)
                analysis_report = f"Workflow updated with versions from {len(installed_nodes)} installed nodes."
            
            return (result, analysis_report)
            
        except Exception as e:
            error_msg = f"Error processing workflow: {str(e)}"
            return (json.dumps(workflow_data, indent=2) if 'workflow_data' in locals() else "{}", error_msg)

# Node mappings
NODE_CLASS_MAPPINGS = {
    "LoadWorkflowFromFile": LoadWorkflowFromFile,
    "SaveWorkflowToFile": SaveWorkflowToFile,
    "WorkflowVersionManager": WorkflowVersionManager,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoadWorkflowFromFile": "Load Workflow From File",
    "SaveWorkflowToFile": "Save Workflow To File", 
    "WorkflowVersionManager": "Workflow Version Manager",
}