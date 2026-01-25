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
        prompt = """You are extracting data from a Ryeland sheep pedigree certificate. This is a VISUAL DOCUMENT with a specific standard layout.

CRITICAL LAYOUT RULES - READ CAREFULLY:
The pedigree is laid out in COLUMNS from left to right:
- Column 1 (LEFTMOST): Main animal (the subject of the certificate)
- Column 2: Parents - SIRE on TOP row, DAM on BOTTOM row
- Column 3: Grandparents - 4 animals in 4 rows
- Column 4: Great-grandparents - 8 animals in 8 rows  
- Column 5: Great-great-grandparents - 16 animals in 16 rows

PARENT IDENTIFICATION - ABSOLUTELY CRITICAL:
Look at Column 2 (parents column) which has TWO boxes:
- The TOP box in Column 2 = SIRE (father) - This connects to the top half of the pedigree
- The BOTTOM box in Column 2 = DAM (mother) - This connects to the bottom half of the pedigree

To identify which is which:
1. Look at the VERTICAL POSITION in Column 2
2. TOP position = sire, BOTTOM position = dam
3. Do NOT rely on registration prefix (M/F) alone - always use POSITION
4. The sire's parents (paternal grandparents) will be in the TOP TWO rows of Column 3
5. The dam's parents (maternal grandparents) will be in the BOTTOM TWO rows of Column 3

GRANDPARENT MAPPING:
Column 3 has 4 boxes from top to bottom:
- Row 1 (topmost): paternalGrandsire (sire's sire)
- Row 2: paternalGranddam (sire's dam)
- Row 3: maternalGrandsire (dam's sire)
- Row 4 (bottommost): maternalGranddam (dam's dam)

For EACH animal extract these fields:
- name: Animal's name (or null if blank/missing)
- registration: Registration number like M12345 or F12345 (required)
- ukRegistration: UK registration in parentheses if present (or null)
- gender: "Male" if M prefix, "Female" if F prefix
- color: Usually "White" (or null if missing)
- birthDate: Format YYYY-MM-DD (or null if missing)

Return ONLY valid JSON in this EXACT structure:
{
  "main": { all fields },
  "parents": {
    "sire": { all fields for TOP animal in Column 2 },
    "dam": { all fields for BOTTOM animal in Column 2 }
  },
  "grandparents": {
    "paternalGrandsire": { Row 1 of Column 3 },
    "paternalGranddam": { Row 2 of Column 3 },
    "maternalGrandsire": { Row 3 of Column 3 },
    "maternalGranddam": { Row 4 of Column 3 }
  },
  "greatGrandparents": [
    { "position": "GGGS1", ... top to bottom of Column 4 ... }
  ],
  "greatGreatGrandparents": [
    { "position": "GGGGS1", ... top to bottom of Column 5 ... }
  ]
}

DOUBLE-CHECK YOUR WORK:
Before returning, verify:
1. The sire (parents.sire) is the TOP box in Column 2
2. The dam (parents.dam) is the BOTTOM box in Column 2
3. All registrations are correctly extracted
4. Return ONLY the JSON with no additional text or markdown"""
        
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
