import os

class Config:
    @staticmethod
    def get_project_root():
        """ Find the project root directory based on a known file or directory in the project. """
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.join(current_dir, '../') 
        return os.path.abspath(project_root)

    @classmethod
    def get_data_dir(cls):
        """ Returns the absolute path to the data directory """
        return os.path.join(cls.get_project_root(), "data")

def get_project_root():
    """ Backward compatible function for the rest of the app """
    return Config.get_project_root()

# def get_config():
#     project_root = get_project_root()
#     config_path = os.path.join(project_root, 'config.yml')
#
#     with open(config_path, 'r') as file:
#         config = yaml.safe_load(file)
#
#     if 'paths' in config:
#         for category, paths_dict in config['paths'].items():
#             for path_key, path_value in paths_dict.items():
#                 # Assume that every entry under 'paths' is a filepath to be updated
#                 config['paths'][category][path_key] = os.path.join(project_root, path_value)
#
#     return config