# OCR Service for PedigreePro
# This processes pedigree images and returns text

from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image
import pytesseract
import io

app = Flask(__name__)
CORS(app)  # Allow requests from your Netlify site

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'running',
        'service': 'PedigreePro OCR Service',
        'version': '1.0'
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'})

@app.route('/process-pedigree', methods=['POST'])
def process_pedigree():
    try:
        # Get uploaded files
        if 'detailsImage' not in request.files or 'pedigreeImage' not in request.files:
            return jsonify({
                'success': False,
                'error': 'Both images required'
            }), 400
        
        details_file = request.files['detailsImage']
        pedigree_file = request.files['pedigreeImage']
        
        # TEST MODE: Process ONLY details image
        print('Processing details image ONLY (test mode)...')
        details_file_content = details_file.read()
        details_img = Image.open(io.BytesIO(details_file_content))
        if details_img.width > 1000:
            details_img.thumbnail((1000, 1000))
        
        details_text = pytesseract.image_to_string(details_img)
        
        # Skip pedigree for now
        print('Skipping pedigree image to save memory...')
        pedigree_text = "TEST MODE: Pedigree processing skipped"
        
        print(f'OCR complete - Details: {len(details_text)} chars')
        
        return jsonify({
            'success': True,
            'detailsText': details_text,
            'pedigreeText': pedigree_text
        })
        
    except Exception as e:
        print(f'Error: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    # Railway/Render sets PORT environment variable
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
