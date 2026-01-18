from flask import Flask, request, jsonify
from flask_cors import CORS
from google.cloud import vision
from PIL import Image
import io
import os

app = Flask(__name__)
CORS(app)

os.environ['GOOGLE_APPLICATION_CREDENTIALS_JSON'] = os.environ.get('GOOGLE_CLOUD_API_KEY', '')

def get_vision_client():
    api_key = os.environ.get('GOOGLE_CLOUD_API_KEY')
    if not api_key:
        raise ValueError("GOOGLE_CLOUD_API_KEY environment variable not set")
    
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
        if 'detailsImage' not in request.files or 'pedigreeImage' not in request.files:
            return jsonify({
                'success': False,
                'error': 'Both images required'
            }), 400
        
        details_file = request.files['detailsImage']
        pedigree_file = request.files['pedigreeImage']
        
        print('Initializing Google Cloud Vision client...')
        client = get_vision_client()
        
        print('Processing details image with Google Vision...')
        details_content = details_file.read()
        details_image = vision.Image(content=details_content)
        details_response = client.text_detection(image=details_image)
        
        if details_response.error.message:
            raise Exception(f'Google Vision error: {details_response.error.message}')
        
        details_text = details_response.text_annotations[0].description if details_response.text_annotations else ""
        print(f'Details OCR complete: {len(details_text)} chars')
        
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

@app.route('/process-sheep-pedigree', methods=['POST'])
def process_sheep_pedigree():
    try:
        print('Received sheep pedigree image processing request')
        
        if 'pedigreeFile' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No image file provided'
            }), 400
        
        image_file = request.files['pedigreeFile']
        print(f'Processing image: {image_file.filename}')
        
        print('Initializing Google Cloud Vision client...')
        client = get_vision_client()
        
        image_content = image_file.read()
        
        print('Calling Google Vision API for image...')
        
        image = vision.Image(content=image_content)
        response = client.text_detection(image=image)
        
        if response.error.message:
            raise Exception(f'Google Vision error: {response.error.message}')
        
        text = response.text_annotations[0].description if response.text_annotations else ""
        
        print(f'OCR complete, extracted {len(text)} characters')
        print(f'First 200 chars: {text[:200]}')
        
        return jsonify({
            'success': True,
            'text': text
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
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
