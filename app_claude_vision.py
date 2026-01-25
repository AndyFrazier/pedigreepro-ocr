from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic
import base64
import os
import json

app = Flask(__name__)
CORS(app)

# Get Anthropic API key from environment
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'running',
        'service': 'PedigreePro OCR Service (Claude Vision)',
        'version': '4.0 - Claude Vision API'
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'})

@app.route('/process-sheep-pedigree', methods=['POST'])
def process_sheep_pedigree():
    try:
        print('Received sheep pedigree processing request')
        
        if 'pedigreeFile' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file provided'
            }), 400
        
        file = request.files['pedigreeFile']
        print(f'Processing file: {file.filename}')
        
        # Read file content
        file_content = file.read()
        
        # Determine media type
        media_type = 'image/jpeg'
        if file.filename.lower().endswith('.pdf'):
            media_type = 'application/pdf'
        elif file.filename.lower().endswith('.png'):
            media_type = 'image/png'
        
        # Encode to base64
        file_base64 = base64.standard_b64encode(file_content).decode('utf-8')
        
        print('Calling Claude Vision API...')
        
        # Initialize Anthropic client
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        
        # Create the prompt for Claude
        prompt = """I need you to extract ALL animals from this Ryeland sheep pedigree certificate and return them as structured JSON.

CRITICAL - PEDIGREE LAYOUT:
The pedigree certificate has a TREE STRUCTURE with the main animal at the TOP and 4 COLUMNS of boxes extending to the RIGHT:

- Main animal: Located at the TOP of the page
- Column 1 (LEFTMOST): 2 boxes containing the PARENTS
  - TOP box (GREY/SHADED) = SIRE (father)
  - BOTTOM box (WHITE) = DAM (mother)
- Column 2: 4 boxes containing GRANDPARENTS
- Column 3: 8 boxes containing GREAT-GRANDPARENTS
- Column 4 (RIGHTMOST): 16 boxes containing GREAT-GREAT-GRANDPARENTS

CRITICAL FOR PARENTS:
- The SIRE is in the TOP GREY BOX of Column 1 (the leftmost column)
- The DAM is in the BOTTOM WHITE BOX of Column 1 (the leftmost column)
- DO NOT read animals from Column 2 or beyond as the parents
- Each box shows the animal's name, registration number, and color

For EACH animal in the pedigree, extract:
- name: Animal's name (or null if missing)
- registration: Registration number like M12345 or F12345
- ukRegistration: UK registration number in parentheses (or null)
- gender: "Male" or "Female" (M prefix = Male, F prefix = Female)
- color: Usually "White" (or null)
- birthDate: In format YYYY-MM-DD (or null)

Return JSON in this EXACT structure:
{
  "main": {
    "name": "...",
    "registration": "...",
    "ukRegistration": "...",
    "gender": "...",
    "color": "...",
    "birthDate": "..."
  },
  "parents": {
    "sire": { ... fields from TOP GREY box in Column 1 ... },
    "dam": { ... fields from BOTTOM WHITE box in Column 1 ... }
  },
  "grandparents": {
    "paternalGrandsire": { ... },
    "paternalGranddam": { ... },
    "maternalGrandsire": { ... },
    "maternalGranddam": { ... }
  },
  "greatGrandparents": [
    { "position": "GGGS1", ... },
    { "position": "GGGD1", ... },
    ... 8 animals total ...
  ],
  "greatGreatGrandparents": [
    { "position": "GGGGS1", ... },
    { "position": "GGGGD1", ... },
    ... 16 animals total ...
  ]
}

IMPORTANT: 
- Male boxes are GREY/SHADED, female boxes are WHITE
- Extract animals from LEFT to RIGHT by column
- Return ONLY valid JSON, no other text
- If a field is missing, use null
"""
        
        # Call Claude API
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document" if media_type == "application/pdf" else "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": file_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        )
        
        # Extract response
        response_text = message.content[0].text
        print(f'Claude response length: {len(response_text)} chars')
        
        # Parse JSON from response
        # Claude might wrap JSON in markdown code blocks
        if '```json' in response_text:
            json_start = response_text.find('```json') + 7
            json_end = response_text.find('```', json_start)
            response_text = response_text[json_start:json_end].strip()
        elif '```' in response_text:
            json_start = response_text.find('```') + 3
            json_end = response_text.find('```', json_start)
            response_text = response_text[json_start:json_end].strip()
        
        pedigree_data = json.loads(response_text)
        
        print('Successfully parsed pedigree data')
        print(f'Main animal: {pedigree_data.get("main", {}).get("name")} {pedigree_data.get("main", {}).get("registration")}')
        
        return jsonify({
            'success': True,
            'pedigree': pedigree_data
        })
        
    except Exception as e:
        print(f'Error: {str(e)}')
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
