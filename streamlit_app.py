import streamlit as st
import json

# Load pathology data from JSON
with open("pathology_data.json", "r") as json_file:
    pathology_data = json.load(json_file)

# Define questions and expected responses
questions = {
    "fall_recently": "Did your shoulder problems start after an impact or fall?",
    "sudden_start": "Did your shoulder pain begin suddenly, or did it develop gradually over time?",
    "unstable": "Does your shoulder feel wobbly or like it might shift out of position, especially when reaching or lifting?",
    "history_of_issues": "Do you have a history of shoulder problems?",
    "stiffness": "How restricted does your shoulder feel when trying to move it?",
    "lifting_pain": "How painful is it to raise your arm?",
    "localized_pain": "How much pain do you feel when pressing directly on the sore area of your shoulder?",
    "weakness_lifting": "How weak does your shoulder feel when lifting objects?"
}

# Define response types with custom labels
custom_answers = {
    "fall_recently": {"No": 0, "Yes": 1},
    "sudden_start": {"Gradually": 0, "Suddenly": 1},
    "unstable": {"No": 0, "Yes": 1},
    "history_of_issues": {"No": 0, "Yes": 1}
}

# Define slider labels for start and end of the scale
slider_labels = {
    "lifting_pain": ["No pain", "Slight discomfort", "Noticable pain", "Severe pain", "Unbearable painful"],
    "stiffness": ["No stiffness", "Slight stiffness", "Moderate stiffness", "Severe stiffness", "Frozen/stuck"],
    "localized_pain": ["No tenderness", "Slight tenderness", "Noticable pain", "Sharp pain", "Extreme pain"],
    "weakness_lifting": ["No weakness", "Slight weakness", "Moderate weakness", "Struggles to lift", "Unable to lift"]
}

# Streamlit UI
st.title("🩺 Shoulder Pain Diagnosis Tool")
st.write("Answer the following questions to get a possible diagnosis.")

# Store user responses
user_responses = {}

# Create UI input fields
for key, question in questions.items():
    if key in custom_answers:  
        # Use custom labels for Yes/No or Gradually/Suddenly questions
        selected_option = st.radio(question, list(custom_answers[key].keys()), format_func=lambda x: x)
        user_responses[key] = custom_answers[key].get(selected_option, 0)  # Convert labels to numerical values
    elif key in slider_labels:
        # Use select_slider to show text-based scale instead of numbers
        user_responses[key] = st.select_slider(question, options=[1, 2, 3, 4, 5], format_func=lambda x: slider_labels[key][x - 1])
    else:
        # Default numeric slider
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
