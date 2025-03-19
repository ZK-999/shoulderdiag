# Store user responses
user_responses = {}

# Create UI input fields
for key, question in questions.items():
    if key in custom_answers:
        # Use custom labels for Yes/No or Gradually/Suddenly questions
        selected_option = st.radio(question, list(custom_answers[key].keys()), format_func=lambda x: x)
        user_responses[key] = custom_answers[key].get(selected_option, 0)  # Avoids KeyError
    else:
        # Use sliders with labels for 1-5 scale questions
        min_label, max_label = slider_labels.get(key, ("Low", "High"))
        user_responses[key] = st.slider(question, 1, 5, 3, format="%d", help=f"{min_label} (1) → {max_label} (5)")
