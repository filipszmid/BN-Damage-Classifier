import os

import yaml


def get_project_root():
    """ Find the project root directory based on a known file or directory in the project. """
    # Assume this script is run from somewhere within the project structure, e.g., 'src/parser'
    # Adjust the path below to correctly point to the project root based on this script's location
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.join(current_dir, '../')  # Adjust the traversal to the project root
    return os.path.abspath(project_root)

def get_config():
    project_root = get_project_root()
    config_path = os.path.join(project_root, 'config.yml')

    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)

    if 'paths' in config:
        for category, paths_dict in config['paths'].items():
            for path_key, path_value in paths_dict.items():
                # Assume that every entry under 'paths' is a filepath to be updated
                config['paths'][category][path_key] = os.path.join(project_root, path_value)

    return config