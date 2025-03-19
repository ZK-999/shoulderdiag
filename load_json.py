import json

# Load the JSON file
with open("pathology_data.json", "r") as json_file:
    pathology_data = json.load(json_file)

# Print to verify the data
print("Loaded Pathology Data:")
print(json.dumps(pathology_data, indent=4))
