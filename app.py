# app.py
import os
import base64
from flask import Flask, render_template, request, redirect, url_for, jsonify
from openai import OpenAI
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize OpenAI client
client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    
    if request.method == 'POST':
        # Check if file was uploaded
        if 'file' not in request.files:
            return render_template('index.html', error="No file part")
        
        file = request.files['file']
        
        if file.filename == '':
            return render_template('index.html', error="No selected file")
        
        if file and allowed_file(file.filename):
            # Save the file
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Analyze the image with OpenAI Vision
            try:
                with open(filepath, "rb") as image_file:
                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                
                response = client.chat.completions.create(
                    model="gpt-4-vision-preview",
                    messages=[
                        {
                            "role": "system",
                            "content": """You are a fashion historian who specializes in determining the temporal origin of clothing items.
                            For each image, identify:
                            1. A specific date (in Month Day, Year format) 
                            2. A specific location
                            3. A brief explanation of why this item belongs to this time and place
                            Keep your explanation to 2-3 sentences."""
                        },
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "What is the temporal origin of this clothing item? When and where would someone wear this?"},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{base64_image}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=300
                )
                
                # Extract the result
                result = {
                    'image_path': filepath,
                    'analysis': response.choices[0].message.content
                }
                
                # Parse the analysis to extract date and location
                analysis_text = response.choices[0].message.content
                
                # Very simple parsing - in production you would use more robust methods
                date = None
                location = None
                explanation = analysis_text
                
                # Attempt to extract date in format like "June 17, 1968"
                import re
                date_match = re.search(r'([A-Z][a-z]+ \d{1,2}, \d{4})', analysis_text)
                if date_match:
                    date = date_match.group(1)
                
                # Try to extract location - more complex, would need enhancement
                location_keywords = ["in", "at", "from"]
                for keyword in location_keywords:
                    location_match = re.search(f'{keyword} ([A-Z][a-z]+ ?[A-Z]?[a-z]*)', analysis_text)
                    if location_match:
                        location = location_match.group(1)
                        break
                
                result['date'] = date
                result['location'] = location
                result['explanation'] = explanation
                
                return render_template('result.html', result=result)
                
            except Exception as e:
                return render_template('index.html', error=f"Error analyzing image: {str(e)}")
    
    return render_template('index.html', result=result)

if __name__ == '__main__':
    app.run(debug=True)
