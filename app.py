from flask import Flask, request, jsonify, render_template, url_for
import openai
import os

app = Flask(__name__)

# Replace with your OpenAI API Key
app.secret_key = os.environ.get('OPENAI_API_KEY')

# Store user responses in memory for simplicity
user_responses = {}

# Structured questions (Q1–Q3) with images
structured_questions = [
    "How are you feeling?",                # Q1
    "What’s the color of your emotion?",   # Q2
    "What’s the shape of your emotion?"    # Q3
]

# Freeform reflective questions (Q4–Q8)
freeform_questions = [
    {"validation": "Thanks for sharing that.", "question": "Can you share what triggered this feeling?"},        # Q4
    {"validation": "I see where you're coming from.", "question": "Could you describe the context of this situation?"}, # Q5
    {"validation": "It’s understandable to feel that way.", "question": "How did you react to the situation?"},               # Q6
    {"validation": "Thanks for reflecting on that.", "question": "How do you feel about the way you reacted?"},        # Q7
    {"validation": None, "question": "Based on your reflections, would you like to create a story?"}  # Q8
]



@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    global user_responses
    # Images for Q1–Q3 initialized here
    image_urls = {
        "How are you feeling?": url_for('static', filename='images/emojis.png'),
        "What’s the color of your emotion?": url_for('static', filename='images/colors.png'),
        "What’s the shape of your emotion?": url_for('static', filename='images/shapes.png')
    }

    user_input = request.json['message']
    conversation = request.json.get('conversation', [])
    next_question_index = len(conversation) // 2

    if next_question_index >= 8:  # All 8 questions answered
        return jsonify({"redirect": "/stories"})

    if next_question_index < len(structured_questions):  # Q1–Q3: Structured questions with images
        next_question = structured_questions[next_question_index]
        image_url = image_urls.get(next_question, None)
        ai_response = next_question
    else:  # Q4–Q8: Freeform reflective questions
        question_data = freeform_questions[next_question_index - len(structured_questions)]
        validation = question_data["validation"]

        # Generate dynamic validation for Q8
        if next_question_index == 7:  # Q8
            previous_responses = {
                "feeling": user_responses.get("Q1", "an emotion"),
                "trigger": user_responses.get("Q4", "something that happened"),
                "context": user_responses.get("Q5", "the surrounding context"),
                "reaction": user_responses.get("Q6", "how you reacted"),
                "reflection": user_responses.get("Q7", "your reflection")
            }
            validation_prompt = (
                f"You are a kind and empathetic therapist. Based on the user's responses: {previous_responses}."
                "Generate a warm, empathetic validation in 1-2 sentences."
            )
            validation_response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "system", "content": "You are a kind and empathetic psychotherapist."},
                          {"role": "user", "content": validation_prompt}]
            )
            validation = validation_response.choices[0].message["content"].strip()

        question = question_data["question"]
        ai_response = f"{validation} {question}" if validation else question
        image_url = None

    # Save the user's response
    user_responses[f"Q{next_question_index + 1}"] = user_input
    conversation.append({"role": "assistant", "content": ai_response})

    return jsonify({"response": ai_response, "conversation": conversation, "image_url": image_url})

@app.route('/stories')
def stories():
    return render_template('stories.html')

@app.route('/generate_stories', methods=['POST'])
def generate_stories():
    global user_responses

    # Collect all user responses as a summary for context
    user_summary = ". ".join([f"Q{i + 1}: {response}" for i, response in enumerate(user_responses.values())])

    # Define the narrative styles and their specific instructions
    narrative_styles = {
        "fact-based": "Write a straightforward summary of the user's responses as a story.",
        "acceptance-based": "Write a story to help the user accept their emotions as they are, based on Acceptance and Commitment Therapy technique.",
        "cognitive reappraisal": "Write a story to help users reframe negative situations in ways that are more positive and adaptive, based on Cognitive Behavioral Therapy technique."
    }

    stories = []

    for style, instruction in narrative_styles.items():
        story_prompt = (
            f"Based on the following user responses: {user_summary}, {instruction} "
            "The story should be human-like and reflecting the user's experience. "
            "Keep the story encouraging and easy to read for 10 years old, address the reader as 'you,' and under 400 characters."
        )
        try:
            story_response = openai.Completion.create(
                model="gpt-4",
                prompt=story_prompt,
                max_tokens=150,
                timeout=30  # Set a timeout for the API call
            )
            story_text = story_response.choices[0].text.strip()
        except Exception as e:
            return jsonify({'error': 'Failed to generate story due to timeout or other API issue.', 'exception': str(e)}), 504

        # Generate an illustration prompt tied to the narrative
        illustration_prompt = (
            f"Create an oil painting illustration inspired by the story: '{story_text}'. Use realistic and descriptive elements "
            "to reflect the overall content of the story."
        )
        illustration_response = openai.Image.create(prompt=illustration_prompt, n=1, size="512x512")
        image_url = illustration_response["data"][0]["url"]

        stories.append({"text": story_text, "image_url": image_url})

    user_responses["generated_stories"] = stories
    return jsonify(stories)


@app.route('/story_selected')
def story_selected():
    selected_index = int(request.args.get('index', 0))
    selected_story = user_responses.get("generated_stories", [])[selected_index]
    user_responses["selected_story"] = selected_story
    return render_template('page3.html', story=selected_story)

@app.route('/final_book')
def final_book():
    final_story = user_responses.get("edited_story", user_responses.get("selected_story", {}).get("text", ""))
    final_drawing = user_responses.get("edited_drawing", user_responses.get("selected_story", {}).get("image_url", ""))
    return render_template('page4.html', story=final_story, drawing=final_drawing)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
