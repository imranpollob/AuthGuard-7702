import yaml

def save_yaml_config(file_path, config):
    with open(file_path, 'w') as file:
        yaml.dump(config, file)

def load_yaml_config(file_path):
    with open(file_path, 'r') as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)

def update_yaml_config(file_path, key_path, value):
    """
    Update a specific value in a YAML file.

    :param file_path: Path to the YAML file.
    :param key_path: The path to the key. Use a list to denote nested paths.
    :param value: The new value to set.
    """
    # Load the current config
    config = load_yaml_config(file_path)
    
    # Reference to the part of the config we're updating
    temp = config
    for key in key_path[:-1]: # Navigate through the nested keys, if any
        temp = temp.setdefault(key, {}) # Create nested dictionaries if necessary
    
    # Update the value
    temp[key_path[-1]] = value
    
    # Save the updated config back to the file
    save_yaml_config(file_path, config)

# Example usage:
# update_yaml_config('config.yaml', ['parent', 'child', 'key'], 'new value')
