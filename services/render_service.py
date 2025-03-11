# services/render_service.py
import io
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt
import re
from PIL import Image
import logging

class RenderService:
    """Service for rendering LaTeX and other content into images"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def render_latex_to_image(self, formula, fontsize=60, dpi=300, format='png'):
        """Renders LaTeX formula to an image with improved clarity and formatting."""
        # Process formula
        formula = formula.replace("\\neq", "&≠")
        formula = formula.replace("\\eq", "!≠")
        formula = formula.replace("\eq", "!!≠")
        formula = formula.replace('\\n', '\n')
        formula = formula.strip().strip('$')
        
        # Configure matplotlib
        plt.rcParams['text.usetex'] = False
        plt.rcParams['mathtext.fontset'] = 'cm'
        plt.rcParams['mathtext.default'] = 'regular'
        
        # Count lines
        line_count = formula.count('\n') + 1
        width = 16
        height = max(8, line_count * 0.8 + 2)
        
        plt.close('all')
        fig = plt.figure(figsize=(width, height), dpi=dpi)
        
        try:
            lines = formula.split('\n')
            line_spacing = 0.8 / max(len(lines), 1)
            start_position = 0.5 + (len(lines) - 1) * line_spacing / 2
            
            for i, line in enumerate(lines):
                line = line.strip()
                if line:
                    y_position = start_position - i * line_spacing
                    plt.text(0.5, y_position, f'${line}$', 
                             fontsize=fontsize,
                             ha='center',
                             va='center',
                             transform=fig.transFigure)
            
            plt.axis('off')
            plt.tight_layout(pad=1.0)
            
            buf = io.BytesIO()
            fig.savefig(buf, format=format, dpi=dpi, bbox_inches='tight', pad_inches=0.2, transparent=True)
            plt.close(fig)
            buf.seek(0)
            
            return buf
        except Exception as e:
            self.logger.error(f"Error rendering LaTeX: {str(e)}")
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
        image_data.seek(0)
        img = Image.open(image_data)
        
        # Check dimensions
        width, height = img.size
        if width > max_width or height > max_height:
            scale_w = max_width / width if width > max_width else 1
            scale_h = max_height / height if height > max_height else 1
            scale = min(scale_w, scale_h)
            
            new_width = int(width * scale)
            new_height = int(height * scale)
            
            img = img.resize((new_width, new_height), Image.LANCZOS)
        
        # Check file size
        temp_buffer = io.BytesIO()
        img.save(temp_buffer, format='PNG')
        current_size = temp_buffer.getvalue().__sizeof__()
        
        if current_size <= max_size_bytes:
            temp_buffer.seek(0)
            return temp_buffer
        
        # Reduce size if needed
        compression_quality = 95
        while compression_quality > 50 and current_size > max_size_bytes:
            temp_buffer = io.BytesIO()
            img.save(temp_buffer, format='PNG', optimize=True, quality=compression_quality)
            current_size = temp_buffer.getvalue().__sizeof__()
            compression_quality -= 5
        
        temp_buffer.seek(0)
        return temp_buffer
    
    def contains_math_formula(self, text):
        """Checks if text contains mathematical notation."""
        patterns = [r'lim', r'\^', r'\\frac', r'/', r'\*', r'sqrt', r'sin|cos|tan', r'\\sum', r'\\int', r'\\to']
        return any(re.search(pattern, text) for pattern in patterns) or re.search(r'\b\d+/\d+\b', text)
        
    def convert_to_latex(self, text):
        """Convert plaintext math notation to LaTeX format"""
        # Basic conversions
        text = re.sub(r'(\d+)/(\d+)', r'\\frac{\1}{\2}', text)  # Convert fractions
        text = re.sub(r'sqrt\(([^)]+)\)', r'\\sqrt{\1}', text)  # Convert square roots
        text = re.sub(r'(\w+)\^(\w+)', r'\1^{\2}', text)        # Convert exponents
        
        return text