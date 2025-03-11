import io
import re
import logging
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib

# Disable external LaTeX usage
matplotlib.rcParams['text.usetex'] = False

# Set up logging - but keep matplotlib logs at WARNING level to avoid verbosity
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('latex_utils')

# Suppress the verbose matplotlib font debugging logs
matplotlib_logger = logging.getLogger('matplotlib')
matplotlib_logger.setLevel(logging.WARNING)  # Only show warnings and higher for matplotlib


def fix_latex_escapes(text):
    """Ensures mathematical expressions are properly formatted."""
    if text is None:
        return ""
    
    # Handle common escape sequences
    text = text.replace("\\\\", "\\")  # Convert double backslash to single
    text = text.replace("_", r"\_")    # Ensure underscores are escaped
    text = text.replace("^", r"\^")    # Escape caret (power symbol)
    
    # Add proper handling for "not equal to" symbol
    text = text.replace("\\neq", "≠")  # Replace LaTeX \neq with Unicode ≠
    text = text.replace("eq0", "≠0")   # Replace eq0 with Unicode ≠0

    return text

def convert_to_latex(text):
    """
    Converts a given text to a LaTeX-compatible format.
    If it already looks like LaTeX math, it is wrapped properly.
    """
    if text is None:
        return ""
        
    text = text.strip()
    if contains_math_formula(text):
        if not text.startswith('$'):
            text = f'${text}$'
    return text

def render_latex_to_image(formula, fontsize=60, dpi=300, format='png'):
    """Renders math expressions using Matplotlib's mathtext."""
    try:
        if formula is None:
            formula = ""
            
        formula = formula.strip()
        formula = fix_latex_escapes(formula)

        # Ensure math mode
        if not formula.startswith('$'):
            formula = f'${formula}$'

        # Count number of text lines to determine height
        line_count = formula.count('\n') + 1
        
        # Adjust figure dimensions based on content length
        width = 16  # Wider figure for better readability
        height = max(8, line_count * 0.8 + 2)  # Scale height based on line count

        # Close any existing figures to prevent caching issues
        plt.close('all')
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
                
                # Render the LaTeX formula
                plt.text(0.5, y_position, line, 
                        fontsize=fontsize,
                        ha='center',
                        va='center',
                        transform=fig.transFigure)

        # Remove axes
        plt.axis('off')
        
        # Use tight layout with padding
        plt.tight_layout(pad=1.0)

        # Save image to buffer
        buf = io.BytesIO()
        fig.savefig(buf, format=format, dpi=dpi, bbox_inches='tight', pad_inches=0.2, transparent=True)
        plt.close(fig)
        buf.seek(0)

        return buf
    except Exception as e:
        logger.warning(f"Math rendering failed: {e}. Falling back to plain text.")
        
        # Create fallback image with error message
        plt.close('all')
        fig = plt.figure(figsize=(10, 5))
        plt.text(0.5, 0.5, "Could not render formula", fontsize=14,
                ha='center', va='center', transform=fig.transFigure)
        plt.axis('off')
        
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=dpi)
        plt.close(fig)
        buf.seek(0)
        
        return buf

def contains_math_formula(text):
    """Detects math notation in a string to decide whether to render it."""
    if text is None:
        return False
        
    math_patterns = [
        r'\\lim', r'\\to', r'\\cdot', r'_', r'\\frac',  # LaTeX-style math
        r'[∫∑∏∞√]', r'\d+/\d+', r"f'\\(x\\)", r"f'",    # Unicode math symbols
        r'\^', r'/', r'\*', r'sqrt', r'sin|cos|tan'     # Common math operators
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in math_patterns)

def check_and_resize_image(image_data, max_size_bytes=2097152):
    """
    Ensures image is under size limit (2MB) and resizes if necessary.
    """
    try:
        current_size = len(image_data.getvalue())

        if current_size <= max_size_bytes:
            image_data.seek(0)
            return image_data

        image_data.seek(0)
        img = Image.open(image_data)

        # Compute scale factor
        scale_factor = (max_size_bytes / current_size) ** 0.5
        new_width = int(img.width * scale_factor * 0.9)  # 10% buffer
        new_height = int(img.height * scale_factor * 0.9)

        resized_img = img.resize((new_width, new_height), Image.LANCZOS)

        output = io.BytesIO()
        resized_img.save(output, format='PNG', optimize=True)
        output.seek(0)

        return output
    except Exception as e:
        logger.error(f"Error resizing image: {e}")
        image_data.seek(0)
        return image_data