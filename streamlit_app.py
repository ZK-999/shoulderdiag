import streamlit as st
import json

# Load pathology data from JSON
with open("pathology_data.json", "r") as json_file:
    pathology_data = json.load(json_file)

# Define questions and expected responses
questions = {
    "fall_recently": "Did you experience trauma or a fall?",
    "lifting_pain": "Does lifting your arm cause pain?",
    "sudden_start": "Did the pain start suddenly?",
    "unstable": "Does your shoulder feel unstable?",
    "stiffness": "Is your shoulder very stiff?",
    "localized_pain": "Do you have localized pain when pressing on the area?",
    "history_of_issues": "Do you have a history of shoulder problems?",
    "weakness_lifting": "Do you feel weakness when lifting objects?"
}

# Define response types (Yes/No or 1-5 Scale)
question_types = {
    "fall_recently": ["No", "Yes"],
    "sudden_start": ["No", "Yes"],
    "unstable": ["No", "Yes"],
    "history_of_issues": ["No", "Yes"],
    "lifting_pain": list(range(1, 6)),
    "stiffness": list(range(1, 6)),
    "localized_pain": list(range(1, 6)),
    "weakness_lifting": list(range(1, 6))
}

# Streamlit UI
st.title("🩺 Shoulder Pain Diagnosis Tool")
st.write("Answer the following questions to get a possible diagnosis.")

# Store user inputs
user_responses = {}

# Create UI input fields
for key, question in questions.items():
    if key in ["fall_recently", "sudden_start", "unstable", "history_of_issues"]:
        user_responses[key] = st.radio(question, [0, 1], format_func=lambda x: "No" if x == 0 else "Yes")
    else:
        user_responses[key] = st.slider(question, 1, 5, 3)

# **Key Tell-Signs with Boosts for Scores of 4 or 5**
key_tell_signs = {
    "GH Dislocation": {"unstable": 1},
    "RC Tear": {"weakness_lifting": [4, 5]},
    "Frozen Shoulder": {"stiffness": 5},
    "Fracture": {"localized_pain": 5}
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
        for key in questions.keys()
    )

    # Boost conditions if key tell-signs (4 or 5) are met
    for key, required_value in key_tell_signs.get(pathology, {}).items():
        if isinstance(required_value, list):
            if user_responses[key] in required_value:
                total_difference -= 3  # Reduce difference, making it more likely
        elif user_responses[key] >= required_value:
            total_difference -= 3  

    likelihood_scores[pathology] = total_difference

# **Run Diagnosis when Button is Clicked**
if st.button("Get Diagnosis"):
    most_likely = min(likelihood_scores, key=likelihood_scores.get)

    # Display results
    st.subheader("📊 Diagnosis Results")
    sorted_results = sorted(likelihood_scores.items(), key=lambda x: x[1])
    
    for pathology, score in sorted_results:
        st.write(f"**{pathology}:** Score = {score}")

    st.success(f"🩺 **Most Likely Condition: {most_likely}**")
