# OCR Service for PedigreePro
# This processes pedigree images and returns text

from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image
import pytesseract
import io
import gc

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
        
        # Process FIRST image (details)
        print('Processing details image...')
        details_file_content = details_file.read()
        details_img = Image.open(io.BytesIO(details_file_content))
        
        # Resize aggressively
        if details_img.width > 1000:
            details_img.thumbnail((1000, 1000))
        
        # Extract text
        details_text = pytesseract.image_to_string(details_img)
        print(f'Details OCR complete: {len(details_text)} chars')
        
        # CRITICAL: Clean up memory before processing second image
        del details_img
        del details_file_content
        gc.collect()  # Force garbage collection
        
        print('Memory cleaned, processing pedigree image...')
        
        # Process SECOND image (pedigree)
        pedigree_file_content = pedigree_file.read()
        pedigree_img = Image.open(io.BytesIO(pedigree_file_content))
        
        # Resize aggressively
        if pedigree_img.width > 1000:
            pedigree_img.thumbnail((1000, 1000))
        
        # Extract text
        pedigree_text = pytesseract.image_to_string(pedigree_img)
        print(f'Pedigree OCR complete: {len(pedigree_text)} chars')
        
        # Clean up
        del pedigree_img
        del pedigree_file_content
        gc.collect()
        
        print('Both images processed successfully!')
        
        return jsonify({
            'success': True,
            'detailsText': details_text,
            'pedigreeText': pedigree_text
        })
        
    except Exception as e:
        print(f'Error: {str(e)}')
        import traceback
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    # Railway/Render sets PORT environment variable
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
