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
    Sort text blocks by pedigree column structure:
    - Pedigrees are read LEFT-TO-RIGHT by columns
    - Within each column, read TOP-TO-BOTTOM
    - Dynamically detects column boundaries based on X-coordinate clustering
    
    Standard pedigree structure:
    - Column 1: Main animal
    - Column 2: Parents (2 boxes)
    - Column 3: Grandparents (4 boxes)
    - Column 4: Great-grandparents (8 boxes)
    
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
    
    print(f'Processing {len(blocks)} text blocks')
    
    # Get unique X positions (left edge of each block)
    x_positions = sorted(set([b['left'] for b in blocks]))
    
    print(f'Found {len(x_positions)} unique X positions')
    
    # Find gaps between X positions to identify column boundaries
    # Large gaps indicate transitions between columns
    gaps = []
    for i in range(len(x_positions) - 1):
        gap_size = x_positions[i + 1] - x_positions[i]
        gaps.append({
            'after_x': x_positions[i],
            'gap_size': gap_size,
            'index': i
        })
    
    # For a 4-column pedigree, we need 3 column boundaries
    # Find the 3 largest gaps
    if len(gaps) < 3:
        # Not enough gaps - fall back to simple left-to-right, top-to-bottom sort
        print('Warning: Could not detect 4 columns, using simple sort')
        sorted_blocks = sorted(blocks, key=lambda b: (b['left'], b['top']))
        sorted_text = '\n'.join([block['text'] for block in sorted_blocks])
        return {
            'text': sorted_text,
            'debug': {
                'warning': 'Not enough gaps detected',
                'totalBlocks': len(blocks),
                'uniqueXPositions': len(x_positions)
            }
        }
    
    gaps.sort(key=lambda g: g['gap_size'], reverse=True)
    top_3_gaps = gaps[:3]
    
    # Sort the boundaries left-to-right
    column_boundaries = sorted([g['after_x'] for g in top_3_gaps])
    
    print(f'Detected column boundaries at X: {column_boundaries}')
    
    # Assign each block to a column based on its X position
    for block in blocks:
        x = block['left']
        if x <= column_boundaries[0]:
            block['column'] = 1
        elif x <= column_boundaries[1]:
            block['column'] = 2
        elif x <= column_boundaries[2]:
            block['column'] = 3
        else:
            block['column'] = 4
    
    # Count blocks per column for verification
    col_counts = {}
    for block in blocks:
        col = block['column']
        col_counts[col] = col_counts.get(col, 0) + 1
    
    print(f'Blocks per column: {col_counts}')
    
    # Sort: first by column (left to right), then by Y within column (top to bottom)
    sorted_blocks = sorted(blocks, key=lambda b: (b['column'], b['top']))
    
    # Create detailed debug info with first few blocks from each column
    blocks_by_column = {}
    for col in [1, 2, 3, 4]:
        col_blocks = [b for b in sorted_blocks if b['column'] == col]
        blocks_by_column[f'column_{col}'] = [
            {'text': b['text'], 'left': b['left'], 'top': b['top']} 
            for b in col_blocks[:5]  # First 5 blocks from each column
        ]
    
    # Reconstruct text in proper pedigree order
    sorted_text = '\n'.join([block['text'] for block in sorted_blocks])
    
    print(f'Successfully sorted {len(blocks)} blocks by column structure')
    
    return {
        'text': sorted_text,
        'debug': {
            'totalBlocks': len(blocks),
            'columnBoundaries': column_boundaries,
            'blocksPerColumn': col_counts,
            'firstBlocksPerColumn': blocks_by_column,
            'top3Gaps': [{'after_x': g['after_x'], 'size': g['gap_size']} for g in top_3_gaps]
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
