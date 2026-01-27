def sort_text_blocks_by_position(text_annotations):
    """
    Sort text blocks by pedigree column structure (left-to-right columns, top-to-bottom within each column).
    Dynamically detects column boundaries.
    """
    if len(text_annotations) <= 1:
        return []
    
    blocks = []
    for annotation in text_annotations[1:]:
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
    
    # Detect columns by clustering X-coordinates
    x_positions = sorted(set([b['left'] for b in blocks]))
    
    # Find gaps in X-coordinates to identify column boundaries
    gaps = []
    for i in range(len(x_positions) - 1):
        gap_size = x_positions[i + 1] - x_positions[i]
        gaps.append({
            'after_x': x_positions[i],
            'gap_size': gap_size,
            'index': i
        })
    
    # Sort by gap size and take the 3 largest gaps as column boundaries
    gaps.sort(key=lambda g: g['gap_size'], reverse=True)
    column_boundaries = sorted([g['after_x'] for g in gaps[:3]])
    
    print(f'Detected column boundaries at X: {column_boundaries}')
    
    # Assign each block to a column
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
    
    # Sort: first by column (left to right), then by Y within column (top to bottom)
    sorted_blocks = sorted(blocks, key=lambda b: (b['column'], b['top']))
    
    # Reconstruct text
    sorted_text = '\n'.join([block['text'] for block in sorted_blocks])
    
    print(f'Sorted {len(blocks)} blocks into 4 columns')
    return sorted_text
