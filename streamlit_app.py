import streamlit as st
import json

# Load pathology data from JSON
with open("pathology_data.json", "r") as json_file:
    pathology_data = json.load(json_file)

st.markdown(
    """
    <style>
        /* 📄 Global font and spacing for better readability */
        html, body, [class*="st-"] {
            font-family: Arial, Verdana, sans-serif !important;
            line-height: 1.7 !important;
        }

        h1, h2, h3 {
            font-size: 22px !important;
        }

        p, label, div {
            font-size: 18px !important;
            color: #1A1A1A;
        }

        /* 🎨 Page background */
        .stApp {
            background-color: #96adb0;
        }

        /* 🔘 Radio button styling */
        div[role="radiogroup"] > label > div:first-child {
            background-color: #003344 !important;
            border: 2px solid #003344 !important;
        }

        div[role="radiogroup"] > label:hover > div:first-child {
            border: 2px solid #003344 !important;
        }


    </style>
    """,
    unsafe_allow_html=True
)





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
    "lifting_pain": ["No pain", "Slight discomfort", "Noticable pain", "Severe pain", "Extreme pain"],
    "stiffness": ["No stiffness", "Slight stiffness", "Moderate stiffness", "Severe stiffness", "Frozen/stuck"],
    "localized_pain": ["No tenderness", "Slight tenderness", "Noticable pain", "Sharp pain", "Extreme pain"],
    "weakness_lifting": ["No weakness", "Slight weakness", "Moderate weakness", "Struggles to lift", "Unable to lift"]
}

# Streamlit UI

st.markdown('<h4 style="font-weight:bold; color:#003344; font-size:40px;">🩺 Shoulder Pain Assessment Tool 🩺</p>', unsafe_allow_html=True)
st.markdown('<span style="color:#8A4B00; font-size:15px;">⚠️ Note: This tool provides a probability-based estimation from your responses. It is NOT a diagnosis or a substitute for professional medical advice. Please consult a professional healthcare provider for proper evaluation and treatment. ⚠️</div>', unsafe_allow_html=True)
st.markdown('<span style="color:#1A1A1A; font-size:25px;">Answer the following questions to get a possible diagnosis:</p>', unsafe_allow_html=True)

# Store user responses
user_responses = {}

# Create UI input fields
for key, question in questions.items():
    if key in custom_answers:  
        # Use custom labels for Yes/No or Gradually/Suddenly questions
        selected_option = st.radio(question, list(custom_answers[key].keys()), format_func=lambda x: x)
        user_responses[key] = custom_answers[key].get(selected_option, 0)  # Convert labels to numerical values
    elif key in slider_labels:
        # Display the question
        st.markdown(f"**{question}**")

        # Create the slider (no visible label)
        col = st.columns([1])[0]
        with col:
            value = st.slider(
                label="",
                min_value=1,
                max_value=5,
                value=3,
                key=key,
                label_visibility="collapsed",
                format=""
            )

        # Show selected label (e.g., 'Moderate pain') above the slider
        st.markdown(
            f"<div style='font-weight:bold; font-size:16px; color:#003344; margin-bottom:0.25rem;'>"
            f"{slider_labels[key][value - 1]}</div>",
            unsafe_allow_html=True
        )

        st.markdown('<span style="line-height:2; color:#003344; font-size:40px;"></p>', unsafe_allow_html=True)
        st.markdown('<span style="line-height:2; color:#003344; font-size:40px;"></p>', unsafe_allow_html=True)

        # Store the user's response
        user_responses[key] = value

    else:
        # Default numeric slider
        user_responses[key] = st.slider(question, 1, 5, 3)

# **Key Tell-Signs with Boosts for Scores of 4 or 5**
key_tell_signs = {
    "Glenohumeral Dislocation/Subluxation": {"unstable": 1},
    "Rotator Cuff Tear": {"weakness_lifting": [4, 5]},
    "Frozen Shoulder": {"stiffness": 5},
    "Fracture": {"localized_pain": 5}
}

# **NEW RULE: If "Unstable" is Yes, filter out other conditions**
if user_responses["unstable"] == 1:
    relevant_conditions = ["Glenohumeral Dislocation/Subluxation", "Instability", "Fracture"]
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

    info_text = pathology_data[most_likely].get("info")
    st.success(f"🩺 **Most Likely Condition: {most_likely}**")
    st.markdown("**Common symptoms & further actions to take:**")
    st.markdown(info_text)
