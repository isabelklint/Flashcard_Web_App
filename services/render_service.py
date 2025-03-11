# services/render_service.py
import io
import matplotlib
matplotlib.use('Agg')  # Set non-interactive backend
import matplotlib.pyplot as plt
import re
from PIL import Image
import logging
import numpy as np

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('render_service')

# Suppress the verbose matplotlib font debugging logs
matplotlib_logger = logging.getLogger('matplotlib')
matplotlib_logger.setLevel(logging.WARNING)  # Only show warnings and higher for matplotlib

class RenderService:
    """Service for rendering LaTeX and other content into images"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Configure matplotlib for math rendering
        plt.rcParams['text.usetex'] = False  # Use built-in mathtext renderer
        plt.rcParams['mathtext.fontset'] = 'cm'  # Computer Modern font
        plt.rcParams['mathtext.default'] = 'regular'  # Default font style
    
    def render_latex_to_image(self, formula, fontsize=60, dpi=300, format='png'):
        """Renders LaTeX formula to an image with improved clarity and formatting."""
        try:
            # Special case handling for common math notation
            formula = formula.replace("eq0", "≠ 0")
            formula = formula.replace("\\neq 0", "≠ 0")
            formula = formula.replace("\\neq0", "≠ 0")
            formula = formula.replace("\\neq", "≠")
            
            # Process formula
            formula = formula.replace('\\n', '\n')
            formula = formula.strip().strip('$')
            
            # Count lines
            line_count = formula.count('\n') + 1
            
            # Calculate figure dimensions based on content length
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
            
            return self.check_and_resize_image(buf)
            
        except Exception as e:
            self.logger.error(f"Error rendering LaTeX: {str(e)}")
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
    
    def check_and_resize_image(self, image_data, max_size_bytes=2097152, max_width=1500, max_height=1000):
        """Resizes image if it exceeds size limit or dimensions."""
        try:
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
            img.save(temp_buffer, format='PNG', optimize=True)
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
        except Exception as e:
            self.logger.error(f"Error resizing image: {str(e)}")
            return image_data
    
    def contains_math_formula(self, text):
        """Checks if text contains mathematical notation."""
        if text is None:
            return False
            
        patterns = [
            r'\\frac', r'\\sqrt', r'\\sum', r'\\int', r'\\lim', r'\\to', r'\\cdot',
            r'\^', r'/', r'\*', r'sin|cos|tan', r'\\neq', r'eq0',
            r'\b\d+/\d+\b', r'[∫∑∏∞√]'
        ]
        return any(re.search(pattern, text) for pattern in patterns)