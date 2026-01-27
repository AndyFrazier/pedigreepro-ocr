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
        'version': '4.0 - Column-based pedigree sorting'
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
        
        # NEW: Sort pedigree text by column structure (left-to-right, top-to-bottom within columns)
        print('Sorting pedigree text blocks by column structure...')
        pedigree_result = sort_pedigree_blocks_by_columns(pedigree_response.text_annotations)
        
        # pedigree_result is now a dict with 'text' and 'debug' keys
        pedigree_text = pedigree_result.get('text', '')
        debug_info = pedigree_result.get('debug', {})
        
        # Fallback to default if sorting fails
        if not pedigree_text:
            print('Column sorting failed, using default text')
            pedigree_text = pedigree_response.text_annotations[0].description if pedigree_response.text_annotations else ""
        
        print(f'Pedigree OCR complete: {len(pedigree_text)} chars')
        print(f'First 500 chars: {pedigree_text[:500]}')
        
        print('Both images processed successfully with Google Vision!')
        
        return jsonify({
            'success': True,
            'detailsText': details_text,
            'pedigreeText': pedigree_text,
            'debugInfo': debug_info  # Add debug info to response
        })
        
    except Exception as e:
        print(f'Error: {str(e)}')
        import traceback
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def sort_pedigree_blocks_by_columns(text_annotations):
    """
    Sort text blocks by pedigree column and box structure using percentage-based grid.
    
    Standard pedigree structure (4 equal columns, read left-to-right):
    - Column 1: Main animal (1 box = 100% height)
    - Column 2: Parents (2 boxes = 50% height each)
    - Column 3: Grandparents (4 boxes = 25% height each)
    - Column 4: Great-grandparents (8 boxes = 12.5% height each)
    
    Returns dict with 'text' and 'debug' keys
    """
    if len(text_annotations) <= 1:
        return {'text': '', 'debug': {}}
    
    # Extract all text blocks with their positions
    blocks = []
    for annotation in text_annotations[1:]:  # Skip index 0 (full text)
        vertices = annotation.bounding_poly.vertices
        x_coords = [v.x for v in vertices]
        y_coords = [v.y for v in vertices]
        
        blocks.append({
            'text': annotation.description,
            'left': min(x_coords),
            'top': min(y_coords),
            'center_x': sum(x_coords) / len(x_coords),
            'center_y': sum(y_coords) / len(y_coords)
        })
    
    if not blocks:
        return {'text': '', 'debug': {}}
    
    print(f'Processing {len(blocks)} text blocks with percentage-based grid')
    
    # Get the actual coordinate space from Google Vision
    min_x = min(b['left'] for b in blocks)
    max_x = max(b['left'] for b in blocks)
    min_y = min(b['top'] for b in blocks)
    max_y = max(b['top'] for b in blocks)
    
    width = max_x - min_x
    height = max_y - min_y
    
    print(f'Coordinate space: X={min_x} to {max_x} (width={width}), Y={min_y} to {max_y} (height={height})')
    
    # Assign each block to a column (simple quarters)
    for block in blocks:
        x_percent = (block['left'] - min_x) / width if width > 0 else 0
        y_percent = (block['top'] - min_y) / height if height > 0 else 0
        
        # Determine column (4 equal quarters)
        if x_percent < 0.25:
            block['column'] = 1
        elif x_percent < 0.5:
            block['column'] = 2
        elif x_percent < 0.75:
            block['column'] = 3
        else:
            block['column'] = 4
        
        # Determine box within column based on column
        if block['column'] == 1:
            # 1 box (100%)
            block['box'] = 0
        elif block['column'] == 2:
            # 2 boxes (50% each)
            block['box'] = 0 if y_percent < 0.5 else 1
        elif block['column'] == 3:
            # 4 boxes (25% each)
            if y_percent < 0.25:
                block['box'] = 0
            elif y_percent < 0.5:
                block['box'] = 1
            elif y_percent < 0.75:
                block['box'] = 2
            else:
                block['box'] = 3
        else:  # column 4
            # 8 boxes (12.5% each)
            block['box'] = int(y_percent * 8)
            if block['box'] >= 8:
                block['box'] = 7  # Cap at 7 (0-7 = 8 boxes)
    
    # Group blocks by (column, box)
    boxes_dict = {}
    for block in blocks:
        key = (block['column'], block['box'])
        if key not in boxes_dict:
            boxes_dict[key] = []
        boxes_dict[key].append(block)
    
    # Sort boxes in reading order (column 1 to 4, top to bottom within each column)
    sorted_keys = sorted(boxes_dict.keys(), key=lambda k: (k[0], k[1]))
    
    # Within each box, sort blocks by Y (top to bottom), then concatenate with newlines
    dog_texts = []
    for key in sorted_keys:
        box_blocks = sorted(boxes_dict[key], key=lambda b: (b['top'], b['left']))
        dog_text = '\n'.join([b['text'] for b in box_blocks])  # Use newlines to preserve structure
        dog_texts.append(dog_text)
    
    # Create dog list for debugging (first 80 chars of each)
    dog_list = []
    for i, dog_text in enumerate(dog_texts):
        preview = dog_text.replace('\n', ' ')[:80]
        dog_list.append(f'Dog {i+1}: {preview}')
    
    # Join all dogs with newlines
    sorted_text = '\n'.join(dog_texts)
    
    print(f'Successfully grouped {len(blocks)} blocks into {len(dog_texts)} dogs')
    
    return {
        'text': sorted_text,
        'debug': {
            'totalBlocks': len(blocks),
            'totalDogs': len(dog_texts),
            'width': int(width),
            'height': int(height),
            'dogList': dog_list  # Add list of dogs to debug output
        }
    }

def sort_text_blocks_by_position(text_annotations):
    """
    Sort text blocks by their visual position (top-to-bottom, left-to-right).
    Used for non-pedigree documents like sheep pedigrees that use different endpoint.
    
    text_annotations[0] is the full text, text_annotations[1:] are individual blocks.
    """
    if len(text_annotations) <= 1:
        return ""
    
    # Skip index 0 (full text) and get individual text blocks
    blocks = []
    for annotation in text_annotations[1:]:
        # Get bounding box vertices
        vertices = annotation.bounding_poly.vertices
        
        # Calculate center point of bounding box
        x_coords = [v.x for v in vertices]
        y_coords = [v.y for v in vertices]
        center_x = sum(x_coords) / len(x_coords)
        center_y = sum(y_coords) / len(y_coords)
        
        blocks.append({
            'text': annotation.description,
            'x': center_x,
            'y': center_y,
            'top': min(y_coords),
            'left': min(x_coords)
        })
    
    # Sort by Y coordinate (top to bottom), then X coordinate (left to right)
    sorted_blocks = sorted(blocks, key=lambda b: (b['top'], b['left']))
    
    # Reconstruct text in visual reading order
    sorted_text = '\n'.join([block['text'] for block in sorted_blocks])
    
    print(f'Sorted {len(blocks)} text blocks by position')
    return sorted_text

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
        
        # Sort text blocks by position
        print('Sorting text blocks by position...')
        sorted_text = sort_text_blocks_by_position(response.text_annotations)
        
        # Fallback to original method if sorting fails
        if not sorted_text:
            print('Position sorting failed, using default text')
            sorted_text = response.text_annotations[0].description if response.text_annotations else ""
        
        print(f'OCR complete, extracted {len(sorted_text)} characters')
        print(f'First 200 chars: {sorted_text[:200]}')
        
        return jsonify({
            'success': True,
            'text': sorted_text
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
