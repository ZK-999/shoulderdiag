import json

# Load pathology data
with open("pathology_data.json", "r") as json_file:
    pathology_data = json.load(json_file)

# Questions and expected inputs
questions = [
    "Did you experience trauma or a fall? (0=No, 1=Yes)",
    "Does lifting your arm cause pain? (1-5)",
    "Did the pain start suddenly? (0=No, 1=Yes)",
    "Does your shoulder feel unstable? (0=No, 1=Yes)",
    "Is your shoulder very stiff? (1-5)",
    "Do you have localized pain when pressing on the area? (1-5)",
    "Do you have a history of shoulder problems? (0=No, 1=Yes)",
    "Do you feel weakness when lifting objects? (1-5)"
]

# Matching question keys to JSON data
question_keys = [
    "fall_recently", "lifting_pain", "sudden_start", "unstable",
    "stiffness", "localized_pain", "history_of_issues", "weakness_lifting"
]

# Get user responses
user_responses = {}
print("\nAnswer each question with the given scale:\n")

for i, question in enumerate(questions):
    while True:
        try:
            response = int(input(f"{question}: "))
            # Yes/No questions should be 0 or 1
            if question_keys[i] in ["fall_recently", "sudden_start", "unstable", "history_of_issues"]:
                if response in [0, 1]:
                    user_responses[question_keys[i]] = response
                    break
                else:
                    print("Please enter 0 for No, 1 for Yes.")
            # 1-5 scale questions should be within range
            else:
                if 1 <= response <= 5:
                    user_responses[question_keys[i]] = response
                    break
                else:
                    print("Please enter a number between 1 and 5.")
        except ValueError:
            print("Invalid input. Please enter a valid number.")

# Key tell-signs for specific conditions (boost score if matched)
key_tell_signs = {
    "GH Dislocation": {"unstable": 1},  # Instability is a strong indicator
    "Tendon Tear": {"weakness_lifting": 4},  # Weakness is key for tendon tear
    "Frozen Shoulder": {"stiffness": 5},  # Severe stiffness must be considered
    "Fracture": {"localized_pain": 5}  # Severe pain indicates fracture
}

# **NEW RULE: If "Unstable" is Yes, filter out other conditions**
if user_responses["unstable"] == 1:
    relevant_conditions = ["GH Dislocation", "Instability", "Fracture"]
else:
    relevant_conditions = pathology_data.keys()  # Keep all conditions if "Unstable" is No

# Compute likelihood scores
likelihood_scores = {}

for pathology, expected_values in pathology_data.items():
    if pathology not in relevant_conditions:
        continue  # Skip conditions that don't match instability filter

    total_difference = sum(
        abs(expected_values.get(key, 0) - user_responses.get(key, 0))
        for key in question_keys
    )

    # Boost scores if user matches key tell-sign symptoms
    for key, required_value in key_tell_signs.get(pathology, {}).items():
        if user_responses[key] >= required_value:
            total_difference -= 3  # Reduce difference, making it more likely

    likelihood_scores[pathology] = total_difference

# Find most likely condition
most_likely = min(likelihood_scores, key=likelihood_scores.get)

# Display results
print("\n--- Diagnosis Results ---")
for pathology, score in sorted(likelihood_scores.items(), key=lambda x: x[1]):
    print(f"{pathology}: Score = {score}")

print(f"\nMost Likely Condition: **{most_likely}**")
