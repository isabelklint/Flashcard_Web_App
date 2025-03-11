# utils/latex_utils.py
import io
import re
import logging
import matplotlib
import matplotlib.pyplot as plt
from PIL import Image

# Disable external LaTeX usage to use matplotlib's built-in rendering
matplotlib.rcParams['text.usetex'] = False

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('latex_utils')

# Suppress the verbose matplotlib font debugging logs
matplotlib_logger = logging.getLogger('matplotlib')
matplotlib_logger.setLevel(logging.WARNING)

def fix_latex_escapes(text):
    """Ensures mathematical expressions are properly formatted."""
    # Special case handling for common math notation
    text = text.replace("eq0", "≠ 0")
    text = text.replace("\\neq 0", "≠ 0")
    text = text.replace("\\neq0", "≠ 0")
    
    # Convert backslashes properly
    text = text.replace("\\\\", "\\")  # Handle escaped backslashes
    text = text.replace("_", "\\_")    # Ensure underscores are escaped
    
    return text

def convert_to_latex(text):
    """
    Converts a given text to a LaTeX-compatible format.
    If it already looks like LaTeX math, it is wrapped properly.
    """
    text = text.strip()
    if contains_math_formula(text):
        if not text.startswith('$'):
            text = f'${text}$'
    return text

def render_latex_to_image(formula, fontsize=60, dpi=300, format='png'):
    """Renders math expressions using Matplotlib without LaTeX."""
    try:
        formula = formula.strip()
        formula = fix_latex_escapes(formula)
        
        # Process any literal \n characters to actual line breaks
        formula = formula.replace('\\n', '\n')
        
        # Strip dollar signs from formula if present
        formula = formula.strip().strip('$')
        
        # Count number of text lines to determine height
        line_count = formula.count('\n') + 1
        
        # Adjust figure dimensions based on content length
        width = 16  # Wider figure for better readability
        height = max(8, line_count * 0.8 + 2)  # Scale height based on line count
        
        # Close any existing figures to prevent caching issues
        plt.close('all')
        
        # Create a figure with proper dimensions
        fig = plt.figure(figsize=(width, height), dpi=dpi)
        
        # Split the formula by line breaks
        lines = formula.split('\n')
        
        # Calculate appropriate spacing between lines
        line_spacing = 0.8 / max(len(lines), 1)
        start_position = 0.5 + (len(lines) - 1) * line_spacing / 2
        
        # Render each line separately with proper spacing
        for i, line in enumerate(lines):
            line = line.strip()
            if line:  # Skip empty lines
                # Calculate vertical position for each line
                y_position = start_position - i * line_spacing
                
                # Render the LaTeX formula with improved font size
                plt.text(0.5, y_position, f'${line}$', 
                        fontsize=fontsize,
                        ha='center',
                        va='center',
                        transform=fig.transFigure)
        
        plt.axis('off')  # Hide axes
        
        # Use tight layout with more padding
        plt.tight_layout(pad=1.0)
        
        # Save to buffer with high DPI for clarity
        buf = io.BytesIO()
        fig.savefig(buf, format=format, dpi=dpi, bbox_inches='tight', pad_inches=0.2, transparent=True)
        plt.close(fig)
        buf.seek(0)
        
        return buf
    except Exception as e:
        logger.error(f"Error rendering LaTeX: {str(e)}")
        # Create a fallback image with error message
        fig = plt.figure(figsize=(10, 5))
        plt.text(0.5, 0.5, f"Could not render formula", fontsize=14,
                ha='center', va='center', transform=fig.transFigure)
        plt.axis('off')
        
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=dpi)
        plt.close(fig)
        buf.seek(0)
        
        return buf

def contains_math_formula(text):
    """Detects math notation in a string to decide whether to render it."""
    math_patterns = [
        r'\\frac', r'\\sqrt', r'\\sum', r'\\int', r'\\lim', r'\\to', r'\\cdot',
        r'\^', r'/', r'\*', r'sin|cos|tan', r'\\neq', r'eq0',
        r'\b\d+/\d+\b', r'[∫∑∏∞√]'
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in math_patterns)

def check_and_resize_image(image_data, max_size_bytes=2097152, max_width=1500, max_height=1000):
    """Resizes image if it exceeds size limit or dimensions."""
    image_data.seek(0)
    img = Image.open(image_data)
    
    # Check dimensions first
    width, height = img.size
    if width > max_width or height > max_height:
        # Calculate scale factor to fit within max dimensions
        scale_w = max_width / width if width > max_width else 1
        scale_h = max_height / height if height > max_height else 1
        scale = min(scale_w, scale_h)
        
        new_width = int(width * scale)
        new_height = int(height * scale)
        
        img = img.resize((new_width, new_height), Image.LANCZOS)
    
    # Now check file size
    temp_buffer = io.BytesIO()
    img.save(temp_buffer, format='PNG')
    current_size = temp_buffer.getvalue().__sizeof__()
    
    if current_size <= max_size_bytes:
        # If already under size limit, return the resized image
        temp_buffer.seek(0)
        return temp_buffer
    
    # Need to further reduce size
    compression_quality = 95
    while compression_quality > 50 and current_size > max_size_bytes:
        temp_buffer = io.BytesIO()
        img.save(temp_buffer, format='PNG', optimize=True, quality=compression_quality)
        current_size = temp_buffer.getvalue().__sizeof__()
        compression_quality -= 5
    
    temp_buffer.seek(0)
    return temp_buffer