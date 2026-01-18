# OCR Service for PedigreePro
# Using Google Cloud Vision API
from flask import Flask, request, jsonify
from flask_cors import CORS
from google.cloud import vision
from PIL import Image
import io
import os

app = Flask(__name__)
CORS(app)

# Set up Google Cloud Vision client
os.environ['GOOGLE_APPLICATION_CREDENTIALS_JSON'] = os.environ.get('GOOGLE_CLOUD_API_KEY', '')

def get_vision_client():
    """Create Vision API client using API key"""
    api_key = os.environ.get('GOOGLE_CLOUD_API_KEY')
    if not api_key:
        raise ValueError("GOOGLE_CLOUD_API_KEY environment variable not set")
    
    # Create client with API key
    from google.cloud.vision_v1 import ImageAnnotatorClient
    from google.api_core.client_options import ClientOptions
    
    client_options = ClientOptions(api_key=api_key)
    return ImageAnnotatorClient(client_options=client_options)

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'running',
        'service': 'PedigreePro OCR Service (Google Vision)',
        'version': '2.0'
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
        
        print('Initializing Google Cloud Vision client...')
        client = get_vision_client()
        
        # Process details image
        print('Processing details image with Google Vision...')
        details_content = details_file.read()
        details_image = vision.Image(content=details_content)
        details_response = client.text_detection(image=details_image)
        
        if details_response.error.message:
            raise Exception(f'Google Vision error: {details_response.error.message}')
        
        details_text = details_response.text_annotations[0].description if details_response.text_annotations else ""
        print(f'Details OCR complete: {len(details_text)} chars')
        
        # Process pedigree image
        print('Processing pedigree image with Google Vision...')
        pedigree_content = pedigree_file.read()
        pedigree_image = vision.Image(content=pedigree_content)
        pedigree_response = client.text_detection(image=pedigree_image)
        
        if pedigree_response.error.message:
            raise Exception(f'Google Vision error: {pedigree_response.error.message}')
        
        pedigree_text = pedigree_response.text_annotations[0].description if pedigree_response.text_annotations else ""
        print(f'Pedigree OCR complete: {len(pedigree_text)} chars')
        
        print('Both images processed successfully with Google Vision!')
        
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

# ========== ADD THIS NEW ENDPOINT HERE ==========
@app.route('/process-sheep-pedigree', methods=['POST'])
def process_sheep_pedigree():
    """Process a sheep pedigree PDF using Google Vision OCR"""
    try:
        print('Received sheep pedigree PDF processing request')
        
        if 'pdfFile' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No PDF file provided'
            }), 400
        
        pdf_file = request.files['pdfFile']
        print(f'Processing PDF: {pdf_file.filename}')
        
        print('Initializing Google Cloud Vision client...')
        client = get_vision_client()
        
        # Read PDF content
        pdf_content = pdf_file.read()
        
        # Convert PDF to image using PIL
        # Google Vision needs images, not PDFs directly
        try:
            from pdf2image import convert_from_bytes
            
            # Convert first page of PDF to image
            images = convert_from_bytes(pdf_content, first_page=1, last_page=1)
            
            if not images:
                raise Exception("Could not convert PDF to image")
            
            # Convert PIL image to bytes
            img_byte_arr = io.BytesIO()
            images[0].save(img_byte_arr, format='PNG')
            img_content = img_byte_arr.getvalue()
            
        except ImportError:
            # If pdf2image not available, return error
            return jsonify({
                'success': False,
                'error': 'PDF conversion library not installed. Please upload an image instead.'
            }), 400
        
        print('Calling Google Vision API for converted PDF image...')
        
        # Create image from converted content
        image = vision.Image(content=img_content)
        response = client.text_detection(image=image)
        
        if response.error.message:
            raise Exception(f'Google Vision error: {response.error.message}')
        
        # Extract text
        text = response.text_annotations[0].description if response.text_annotations else ""
        
        print(f'OCR complete, extracted {len(text)} characters')
        print(f'First 200 chars: {text[:200]}')
        
        return jsonify({
            'success': True,
            'text': text
        })
        
    except Exception as e:
        print(f'Error processing PDF: {str(e)}')
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
```

**Also need to add `pdf2image` to requirements.txt:**

Add this line to your `requirements.txt` on Render:
```
pdf2image==1.16.3
# ========== END OF NEW ENDPOINT ==========

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
