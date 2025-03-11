# services/presentation_service.py
import io
import csv
import time
import random
import re
import logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('presentation_service')

class PresentationService:
    def __init__(self):
        # Define consistent styling for slides
        self.COLORS = {
            'primary_blue': {'red': 0.0, 'green': 0.4, 'blue': 0.8},
            'dark_text': {'red': 0.2, 'green': 0.2, 'blue': 0.2},
            'light_gray_bg': {'red': 0.97, 'green': 0.97, 'blue': 0.98}
        }
        
        self.FONT_SIZES = {
            'title': 44,
            'subtitle': 28,
            'heading': 40,
            'body': 36,
            'notes': 24
        }
        
    def create_from_csv(self, user_credentials, csv_file, title):
        """Creates a presentation from a CSV file using user's credentials"""
        try:
            # Build services with user credentials
            slides_service = build('slides', 'v1', credentials=user_credentials)
            drive_service = build('drive', 'v3', credentials=user_credentials)
            
            # Read CSV file content
            csv_content = csv_file.read().decode('utf-8')
            csv_io = io.StringIO(csv_content)
            reader = csv.DictReader(csv_io)
            slides_data = list(reader)
            
            # Create presentation in user's Drive
            file_metadata = {'name': title, 'mimeType': 'application/vnd.google-apps.presentation'}
            file = self._execute_with_backoff(drive_service.files().create(body=file_metadata))
            presentation_id = file.get('id')
            
            # Process each slide
            for row in slides_data:
                row_type = row.get('Type', '').lower()
                
                if row_type == 'title':
                    self._create_title_slide(slides_service, drive_service, presentation_id, row.get('Content'), row.get('Notes'))
                elif row_type == 'question':
                    self._create_question_slide(slides_service, drive_service, presentation_id, row.get('Number', ''), row.get('Content'))
                elif row_type == 'answer':
                    self._create_answer_slide(slides_service, drive_service, presentation_id, row.get('Number', ''), row.get('Content'))
                elif row_type == 'transition':
                    self._create_transition_slides(slides_service, drive_service, presentation_id, row.get('Content'))
                else:
                    # Default slide creation
                    self._create_basic_slide(slides_service, presentation_id, row.get('Content'), row.get('Notes', ''))
            
            return {
                'id': presentation_id,
                'url': f"https://docs.google.com/presentation/d/{presentation_id}/edit",
                'title': title
            }
        except Exception as e:
            logger.error(f"Error creating presentation: {str(e)}")
            raise
    
    def _execute_with_backoff(self, request, max_retries=5):
        """Execute a Google API request with exponential backoff for rate limiting."""
        for retry in range(max_retries):
            try:
                return request.execute()
            except HttpError as error:
                if error.resp.status == 429 and retry < max_retries - 1:
                    # Calculate backoff time with exponential increase and jitter
                    sleep_time = (2 ** retry) + random.random()
                    logger.warning(f"Rate limit exceeded. Retrying in {sleep_time:.2f} seconds (attempt {retry+1}/{max_retries})")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"API request failed: {error}")
                    raise
        raise Exception("Max retries exceeded")
    
    def _create_title_slide(self, service, drive_service, presentation_id, title, subtitle=None):
        """Create a standard title slide with title and optional subtitle"""
        try:
            # Create a slide with TITLE layout
            requests = [
                {
                    'createSlide': {
                        'slideLayoutReference': {
                            'predefinedLayout': 'TITLE'
                        }
                    }
                }
            ]
            
            response = self._execute_with_backoff(service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': requests}
            ))
            
            slide_id = response.get('replies')[0].get('createSlide').get('objectId')
            
            # Add delay between API calls
            time.sleep(1)
            
            # Get the placeholders on the slide
            presentation = self._execute_with_backoff(service.presentations().get(
                presentationId=presentation_id
            ))
            
            # Find the slide we just created
            slide = None
            for s in presentation.get('slides', []):
                if s.get('objectId') == slide_id:
                    slide = s
                    break
            
            if not slide:
                logger.error("Couldn't find the created slide.")
                return slide_id
            
            # Find title and subtitle placeholders
            title_placeholder_id = None
            subtitle_placeholder_id = None
            
            for element in slide.get('pageElements', []):
                shape = element.get('shape', {})
                placeholder = shape.get('placeholder', {})
                if placeholder.get('type') == 'TITLE':
                    title_placeholder_id = element.get('objectId')
                elif placeholder.get('type') == 'SUBTITLE':
                    subtitle_placeholder_id = element.get('objectId')
            
            # Update title text if we found the placeholder
            requests = []
            if title_placeholder_id:
                requests.append({
                    'insertText': {
                        'objectId': title_placeholder_id,
                        'text': title
                    }
                })
                
                # Update title style with blue color and bold
                requests.append({
                    'updateTextStyle': {
                        'objectId': title_placeholder_id,
                        'style': {
                            'bold': True,
                            'fontSize': {
                                'magnitude': self.FONT_SIZES['title'],
                                'unit': 'PT'
                            },
                            'foregroundColor': {
                                'opaqueColor': {
                                    'rgbColor': self.COLORS['primary_blue']
                                }
                            }
                        },
                        'fields': 'fontSize'
                    }
                })
                
                # Check if body contains bullet points (lines starting with - or *)
                if any(line.strip().startswith(('-', '*')) for line in body.split('\n')):
                    # Convert bullet points
                    text_requests.append({
                        'createParagraphBullets': {
                            'objectId': body_placeholder_id,
                            'textRange': {
                                'type': 'ALL'
                            },
                            'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE'
                        }
                    })
                else:
                    # Center align if not bullets
                    text_requests.append({
                        'updateParagraphStyle': {
                            'objectId': body_placeholder_id,
                            'style': {
                                'alignment': 'CENTER'
                            },
                            'fields': 'alignment'
                        }
                    })
            
            # Execute the text insertion requests if any
            if text_requests:
                self._execute_with_backoff(service.presentations().batchUpdate(
                    presentationId=presentation_id, 
                    body={'requests': text_requests}
                ))
            
            return slide_id
        except Exception as e:
            logger.error(f"Error creating basic slide: {str(e)}")
            raise
    
    def _contains_math_formula(self, text):
        """Checks if text contains mathematical notation."""
        patterns = [
            r'\\frac', r'\\sqrt', r'\\sum', r'\\int', r'\\lim', r'\\to', r'\\cdot',
            r'\^', r'/', r'\*', r'sin|cos|tan', r'\\neq', r'eq0',
            r'\b\d+/\d+\b', r'[∫∑∏∞√]'
        ]
        return any(re.search(pattern, text) for pattern in patterns)
    
    def _render_latex_to_image(self, formula, fontsize=60, dpi=300, format='png'):
        """Renders LaTeX formula to an image with improved clarity and formatting."""
        try:
            # Import required libraries here to avoid dependencies unless needed
            import matplotlib
            import matplotlib.pyplot as plt
            from PIL import Image
            
            # Configure matplotlib for math rendering
            matplotlib.rcParams['text.usetex'] = False  # Use built-in mathtext renderer
            matplotlib.rcParams['mathtext.fontset'] = 'cm'  # Computer Modern font
            matplotlib.rcParams['mathtext.default'] = 'regular'  # Default font style
            
            # Special case handling for common math notation
            formula = formula.replace("eq0", "≠ 0")
            formula = formula.replace("\\neq 0", "≠ 0")
            formula = formula.replace("\\neq0", "≠ 0")
            
            # Process any literal \n characters to actual line breaks
            formula = formula.replace('\\n', '\n')
            
            # Strip dollar signs from formula if present
            formula = formula.strip().strip(''bold,fontSize,foregroundColor'
                    }
                })
                
                # Center align the title
                requests.append({
                    'updateParagraphStyle': {
                        'objectId': title_placeholder_id,
                        'style': {
                            'alignment': 'CENTER'
                        },
                        'fields': 'alignment'
                    }
                })
            
            # Update subtitle text if we found the placeholder and subtitle is provided
            if subtitle_placeholder_id and subtitle:
                requests.append({
                    'insertText': {
                        'objectId': subtitle_placeholder_id,
                        'text': subtitle
                    }
                })
                
                # Update subtitle style
                requests.append({
                    'updateTextStyle': {
                        'objectId': subtitle_placeholder_id,
                        'style': {
                            'fontSize': {
                                'magnitude': self.FONT_SIZES['subtitle'],
                                'unit': 'PT'
                            }
                        },
                        'fields': 'fontSize'
                    }
                })
                
                # Center align the subtitle
                requests.append({
                    'updateParagraphStyle': {
                        'objectId': subtitle_placeholder_id,
                        'style': {
                            'alignment': 'CENTER'
                        },
                        'fields': 'alignment'
                    }
                })
            
            if requests:
                self._execute_with_backoff(service.presentations().batchUpdate(
                    presentationId=presentation_id,
                    body={'requests': requests}
                ))
            
            return slide_id
        except Exception as e:
            logger.error(f"Error creating title slide: {str(e)}")
            raise
        
    def _create_question_slide(self, service, drive_service, presentation_id, question_number, question_text):
        """Create a slide with a question"""
        try:
            # First create a blank slide with TITLE_AND_BODY layout
            requests = [
                {
                    'createSlide': {
                        'slideLayoutReference': {
                            'predefinedLayout': 'TITLE_AND_BODY'
                        }
                    }
                }
            ]
            
            response = self._execute_with_backoff(service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': requests}
            ))
            
            slide_id = response.get('replies')[0].get('createSlide').get('objectId')
            
            # Add delay between API calls
            time.sleep(1)
            
            # Get the placeholders on the slide
            presentation = self._execute_with_backoff(service.presentations().get(
                presentationId=presentation_id
            ))
            
            # Find the slide we just created
            slide = None
            for s in presentation.get('slides', []):
                if s.get('objectId') == slide_id:
                    slide = s
                    break
            
            if not slide:
                logger.error("Couldn't find the created slide.")
                return slide_id
            
            # Find title and body placeholders
            title_placeholder_id = None
            body_placeholder_id = None
            
            for element in slide.get('pageElements', []):
                shape = element.get('shape', {})
                placeholder = shape.get('placeholder', {})
                if placeholder.get('type') == 'TITLE':
                    title_placeholder_id = element.get('objectId')
                elif placeholder.get('type') == 'BODY':
                    body_placeholder_id = element.get('objectId')
            
            # Update title text if we found the placeholder
            requests = []
            if title_placeholder_id:
                requests.append({
                    'insertText': {
                        'objectId': title_placeholder_id,
                        'text': f'Question {question_number}'
                    }
                })
                
                # Update text style with blue color and bold
                requests.append({
                    'updateTextStyle': {
                        'objectId': title_placeholder_id,
                        'style': {
                            'bold': True,
                            'fontSize': {
                                'magnitude': self.FONT_SIZES['heading'],
                                'unit': 'PT'
                            },
                            'foregroundColor': {
                                'opaqueColor': {
                                    'rgbColor': self.COLORS['primary_blue']
                                }
                            }
                        },
                        'fields': 'bold,fontSize,foregroundColor'
                    }
                })
                
                # Center align the title
                requests.append({
                    'updateParagraphStyle': {
                        'objectId': title_placeholder_id,
                        'style': {
                            'alignment': 'CENTER'
                        },
                        'fields': 'alignment'
                    }
                })
            
            # Update body text if we found the placeholder
            if body_placeholder_id:
                # Replace any literal \n with actual newlines
                if question_text:
                    question_text = question_text.replace('\\n', '\n')
                else:
                    question_text = ""
                
                # First add the text
                requests.append({
                    'insertText': {
                        'objectId': body_placeholder_id,
                        'text': question_text
                    }
                })
                
                # Check if body contains bullet points (lines starting with - or *)
                if question_text and any(line.strip().startswith(('-', '*')) for line in question_text.split('\n')):
                    # Convert bullet points
                    requests.append({
                        'createParagraphBullets': {
                            'objectId': body_placeholder_id,
                            'textRange': {
                                'type': 'ALL'
                            },
                            'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE'
                        }
                    })
                    
                # Then update text style
                requests.append({
                    'updateTextStyle': {
                        'objectId': body_placeholder_id,
                        'style': {
                            'fontSize': {
                                'magnitude': self.FONT_SIZES['body'],
                                'unit': 'PT'
                            }
                        },
                        'fields': 'fontSize'
                    }
                })
                
                # Lastly, update paragraph styling
                requests.append({
                    'updateParagraphStyle': {
                        'objectId': body_placeholder_id,
                        'style': {
                            'alignment': 'CENTER',
                            'spaceAbove': {
                                'magnitude': 20,  # Add 20pt space above the body text
                                'unit': 'PT'
                            }
                        },
                        'fields': 'alignment,spaceAbove'
                    }
                })
            
            if requests:
                self._execute_with_backoff(service.presentations().batchUpdate(
                    presentationId=presentation_id,
                    body={'requests': requests}
                ))
            
            return slide_id
        except Exception as e:
            logger.error(f"Error creating question slide: {str(e)}")
            raise
        
    def _create_answer_slide(self, service, drive_service, presentation_id, answer_number, answer_text):
        """Create a slide with an answer"""
        try:
            # First create a blank slide with TITLE_AND_BODY layout
            requests = [
                {
                    'createSlide': {
                        'slideLayoutReference': {
                            'predefinedLayout': 'TITLE_AND_BODY'
                        }
                    }
                }
            ]
            
            response = self._execute_with_backoff(service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': requests}
            ))
            
            slide_id = response.get('replies')[0].get('createSlide').get('objectId')
            
            # Add delay between API calls
            time.sleep(1)
            
            # Get the slide to find the placeholder IDs
            presentation = self._execute_with_backoff(service.presentations().get(
                presentationId=presentation_id
            ))
            
            # Find the created slide and its placeholders
            title_placeholder_id = None
            body_placeholder_id = None
            
            for slide in presentation.get('slides', []):
                if slide.get('objectId') == slide_id:
                    for element in slide.get('pageElements', []):
                        shape = element.get('shape', {})
                        placeholder = shape.get('placeholder', {})
                        if placeholder.get('type') == 'TITLE':
                            title_placeholder_id = element.get('objectId')
                        elif placeholder.get('type') == 'BODY':
                            body_placeholder_id = element.get('objectId')
            
            # Set the title if we found the title placeholder
            requests = []
            if title_placeholder_id:
                requests.append({
                    'insertText': {
                        'objectId': title_placeholder_id,
                        'text': f'Answer {answer_number}'
                    }
                })
                
                # Style the title
                requests.append({
                    'updateTextStyle': {
                        'objectId': title_placeholder_id,
                        'style': {
                            'bold': True,
                            'fontSize': {
                                'magnitude': self.FONT_SIZES['heading'],
                                'unit': 'PT'
                            },
                            'foregroundColor': {
                                'opaqueColor': {
                                    'rgbColor': self.COLORS['primary_blue']
                                }
                            }
                        },
                        'fields': 'bold,fontSize,foregroundColor'
                    }
                })
                
                # Center align the title
                requests.append({
                    'updateParagraphStyle': {
                        'objectId': title_placeholder_id,
                        'style': {
                            'alignment': 'CENTER'
                        },
                        'fields': 'alignment'
                    }
                })
            
            if answer_text is None:
                answer_text = ""
                
            # Check if answer has math formulas
            if answer_text and self._contains_math_formula(answer_text):
                # If we have LaTeX, we'll try to render it as an image
                try:
                    image_data = self._render_latex_to_image(answer_text)
                    if image_data:
                        # Upload image to Drive
                        file_metadata = {
                            'name': f'latex_formula_{slide_id}.png',
                            'mimeType': 'image/png'
                        }
                        
                        media = MediaIoBaseUpload(image_data, mimetype='image/png')
                        file = self._execute_with_backoff(drive_service.files().create(
                            body=file_metadata,
                            media_body=media,
                            fields='id'
                        ))
                        
                        image_file_id = file.get('id')
                        
                        # Make the file accessible to anyone with the link
                        self._execute_with_backoff(drive_service.permissions().create(
                            fileId=image_file_id,
                            body={'type': 'anyone', 'role': 'reader'},
                            fields='id'
                        ))
                        
                        # Get the slide dimensions
                        slide_width = 720  # Default Google Slides width
                        slide_height = 405  # Default Google Slides height
                        
                        # Calculate image dimensions
                        image_width = 680  # Almost full width
                        image_height = 300  # Reasonable height for formula
                        
                        # Center the image on the slide
                        x_position = (slide_width - image_width) / 2
                        y_position = 200  # Position below title
                        
                        # Add image to slide request
                        requests.append({
                            'createImage': {
                                'url': f'https://drive.google.com/uc?id={image_file_id}',
                                'elementProperties': {
                                    'pageObjectId': slide_id,
                                    'size': {
                                        'width': {'magnitude': image_width, 'unit': 'PT'},
                                        'height': {'magnitude': image_height, 'unit': 'PT'}
                                    },
                                    'transform': {
                                        'scaleX': 1,
                                        'scaleY': 1,
                                        'translateX': x_position,
                                        'translateY': y_position,
                                        'unit': 'PT'
                                    }
                                }
                            }
                        })
                except Exception as e:
                    logger.error(f"Error rendering LaTeX: {e}")
                    # Fall back to text if LaTeX rendering fails
                    if body_placeholder_id:
                        # Replace any literal \n with actual newlines
                        answer_text = answer_text.replace('\\n', '\n')
                        
                        requests.append({
                            'insertText': {
                                'objectId': body_placeholder_id,
                                'text': answer_text
                            }
                        })
                        
                        # Style the text
                        requests.append({
                            'updateTextStyle': {
                                'objectId': body_placeholder_id,
                                'style': {
                                    'fontSize': {
                                        'magnitude': self.FONT_SIZES['body'],
                                        'unit': 'PT'
                                    }
                                },
                                'fields': 'fontSize'
                            }
                        })
            else:
                # Just regular text, no LaTeX
                if body_placeholder_id:
                    # Replace any literal \n with actual newlines
                    if answer_text:
                        answer_text = answer_text.replace('\\n', '\n')
                    
                    requests.append({
                        'insertText': {
                            'objectId': body_placeholder_id,
                            'text': answer_text
                        }
                    })
                    
                    # Style the text
                    requests.append({
                        'updateTextStyle': {
                            'objectId': body_placeholder_id,
                            'style': {
                                'fontSize': {
                                    'magnitude': self.FONT_SIZES['body'],
                                    'unit': 'PT'
                                }
                            },
                            'fields': 'fontSize'
                        }
                    })
                    
                    # Check if body contains bullet points
                    if answer_text and any(line.strip().startswith(('-', '*')) for line in answer_text.split('\n')):
                        # Convert bullet points
                        requests.append({
                            'createParagraphBullets': {
                                'objectId': body_placeholder_id,
                                'textRange': {
                                    'type': 'ALL'
                                },
                                'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE'
                            }
                        })
                    else:
                        # Center align if not a bullet list
                        requests.append({
                            'updateParagraphStyle': {
                                'objectId': body_placeholder_id,
                                'style': {
                                    'alignment': 'CENTER'
                                },
                                'fields': 'alignment'
                            }
                        })
            
            # Execute all requests
            if requests:
                self._execute_with_backoff(service.presentations().batchUpdate(
                    presentationId=presentation_id,
                    body={'requests': requests}
                ))
            
            return slide_id
        except Exception as e:
            logger.error(f"Error creating answer slide: {str(e)}")
            raise
        
    def _create_transition_slides(self, service, drive_service, presentation_id, text, font_size=32):
        """Create transition slides with improved formatting"""
        try:
            # Create a blank slide
            requests = [
                {
                    'createSlide': {
                        'slideLayoutReference': {
                            'predefinedLayout': 'BLANK'
                        }
                    }
                }
            ]
            
            response = self._execute_with_backoff(service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': requests}
            ))
            
            slide_id = response.get('replies')[0].get('createSlide').get('objectId')
            
            # Add delay between API calls
            time.sleep(1)
            
            # Create a text box that takes up more of the slide
            textbox_id = f'textbox_{slide_id}'
            requests = [
                {
                    'createShape': {
                        'objectId': textbox_id,
                        'shapeType': 'TEXT_BOX',
                        'elementProperties': {
                            'pageObjectId': slide_id,
                            'size': {
                                'width': {'magnitude': 650, 'unit': 'PT'},
                                'height': {'magnitude': 350, 'unit': 'PT'}
                            },
                            'transform': {
                                'scaleX': 1,
                                'scaleY': 1,
                                'translateX': 85,  # More centered
                                'translateY': 100,
                                'unit': 'PT'
                            }
                        }
                    }
                }
            ]
            
            self._execute_with_backoff(service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': requests}
            ))
            
            # Add delay between API calls
            time.sleep(1)
            
            # Process any literal \n characters to actual line breaks
            if text:
                text = text.replace('\\n', '\n')
                
                # Remove pagination markers and clean text
                formatted_text = text.replace(" (1/2)", "").replace(" (2/2)", "")
                formatted_text = formatted_text.replace("(1/2)", "").replace("(2/2)", "")
            else:
                formatted_text = ""
            
            # Insert text
            text_style_request = {
                'insertText': {
                    'objectId': textbox_id,
                    'text': formatted_text
                }
            }
            
            self._execute_with_backoff(service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': [text_style_request]}
            ))
            
            # Format text with proper font size and color
            style_request = {
                'updateTextStyle': {
                    'objectId': textbox_id,
                    'style': {
                        'fontSize': {
                            'magnitude': font_size,
                            'unit': 'PT'
                        },
                        'foregroundColor': {
                            'opaqueColor': {
                                'rgbColor': self.COLORS['primary_blue']
                            }
                        }
                    },
                    'fields': 'fontSize,foregroundColor'
                }
            }
            
            self._execute_with_backoff(service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': [style_request]}
            ))
            
            # Check if text contains bullet points and format appropriately
            if formatted_text and any(line.strip().startswith(('-', '*')) for line in formatted_text.split('\n')):
                # Apply bullet styling
                bullets_request = {
                    'createParagraphBullets': {
                        'objectId': textbox_id,
                        'textRange': {
                            'type': 'ALL'
                        },
                        'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE'
                    }
                }
                
                self._execute_with_backoff(service.presentations().batchUpdate(
                    presentationId=presentation_id,
                    body={'requests': [bullets_request]}
                ))
            else:
                # Center align text if not bullets
                paragraph_style_request = {
                    'updateParagraphStyle': {
                        'objectId': textbox_id,
                        'style': {
                            'alignment': 'CENTER',
                            'lineSpacing': 180,
                            'spaceAbove': {
                                'magnitude': 10,
                                'unit': 'PT'
                            },
                            'spaceBelow': {
                                'magnitude': 10,
                                'unit': 'PT'
                            }
                        },
                        'fields': 'alignment,lineSpacing,spaceAbove,spaceBelow'
                    }
                }
                
                self._execute_with_backoff(service.presentations().batchUpdate(
                    presentationId=presentation_id,
                    body={'requests': [paragraph_style_request]}
                ))
            
            return slide_id
        except Exception as e:
            logger.error(f"Error creating transition slide: {str(e)}")
            raise
        
    def _create_basic_slide(self, service, presentation_id, title, body=None):
        """Creates a basic slide with a title and optional body text."""
        try:
            # First create the slide with the TITLE_AND_BODY layout
            requests = [{'createSlide': {'slideLayoutReference': {'predefinedLayout': 'TITLE_AND_BODY'}}}]
            response = self._execute_with_backoff(service.presentations().batchUpdate(
                presentationId=presentation_id, 
                body={'requests': requests}
            ))
            
            slide_id = response['replies'][0]['createSlide']['objectId']
            
            # Get the slide to find the placeholder IDs
            slide_response = self._execute_with_backoff(service.presentations().get(
                presentationId=presentation_id
            ))
            
            # Find the created slide and its placeholders
            title_placeholder_id = None
            body_placeholder_id = None
            
            for slide in slide_response.get('slides', []):
                if slide.get('objectId') == slide_id:
                    for element in slide.get('pageElements', []):
                        shape = element.get('shape', {})
                        placeholder = shape.get('placeholder', {})
                        if placeholder.get('type') == 'TITLE':
                            title_placeholder_id = element.get('objectId')
                        elif placeholder.get('type') == 'BODY':
                            body_placeholder_id = element.get('objectId')
            
            # Prepare requests for inserting text
            text_requests = []
            
            # Process any literal \n characters to actual line breaks
            if title:
                title = title.replace('\\n', '\n')
            else:
                title = ""
            
            if body:
                body = body.replace('\\n', '\n')
            
            # Insert title text if we found the title placeholder
            if title_placeholder_id and title:
                text_requests.append({
                    'insertText': {
                        'objectId': title_placeholder_id,
                        'text': title
                    }
                })
                
                # Style the title
                text_requests.append({
                    'updateTextStyle': {
                        'objectId': title_placeholder_id,
                        'style': {
                            'fontSize': {
                                'magnitude': self.FONT_SIZES['heading'],
                                'unit': 'PT'
                            },
                            'foregroundColor': {
                                'opaqueColor': {
                                    'rgbColor': self.COLORS['primary_blue']
                                }
                            },
                            'bold': True
                        },
                        'fields': 'fontSize,foregroundColor,bold'
                    }
                })
                
                # Center the title
                text_requests.append({
                    'updateParagraphStyle': {
                        'objectId': title_placeholder_id,
                        'style': {
                            'alignment': 'CENTER'
                        },
                        'fields': 'alignment'
                    }
                })
            
            # Insert body text if we found the body placeholder and body is provided
            if body_placeholder_id and body:
                text_requests.append({
                    'insertText': {
                        'objectId': body_placeholder_id,
                        'text': body
                    }
                })
                
                # Style the body text
                text_requests.append({
                    'updateTextStyle': {
                        'objectId': body_placeholder_id,
                        'style': {
                            'fontSize': {
                                'magnitude': self.FONT_SIZES['body'],
                                'unit': 'PT'
                            }
                        },
                        'fields': )
            
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
                    plt.text(0.5, y_position, f'${line}'bold,fontSize,foregroundColor'
                    }
                })
                
                # Center align the title
                requests.append({
                    'updateParagraphStyle': {
                        'objectId': title_placeholder_id,
                        'style': {
                            'alignment': 'CENTER'
                        },
                        'fields': 'alignment'
                    }
                })
            
            # Update subtitle text if we found the placeholder and subtitle is provided
            if subtitle_placeholder_id and subtitle:
                requests.append({
                    'insertText': {
                        'objectId': subtitle_placeholder_id,
                        'text': subtitle
                    }
                })
                
                # Update subtitle style
                requests.append({
                    'updateTextStyle': {
                        'objectId': subtitle_placeholder_id,
                        'style': {
                            'fontSize': {
                                'magnitude': self.FONT_SIZES['subtitle'],
                                'unit': 'PT'
                            }
                        },
                        'fields': 'fontSize'
                    }
                })
                
                # Center align the subtitle
                requests.append({
                    'updateParagraphStyle': {
                        'objectId': subtitle_placeholder_id,
                        'style': {
                            'alignment': 'CENTER'
                        },
                        'fields': 'alignment'
                    }
                })
            
            if requests:
                self._execute_with_backoff(service.presentations().batchUpdate(
                    presentationId=presentation_id,
                    body={'requests': requests}
                ))
            
            return slide_id
        except Exception as e:
            logger.error(f"Error creating title slide: {str(e)}")
            raise
        
    def _create_question_slide(self, service, drive_service, presentation_id, question_number, question_text):
        """Create a slide with a question"""
        try:
            # First create a blank slide with TITLE_AND_BODY layout
            requests = [
                {
                    'createSlide': {
                        'slideLayoutReference': {
                            'predefinedLayout': 'TITLE_AND_BODY'
                        }
                    }
                }
            ]
            
            response = self._execute_with_backoff(service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': requests}
            ))
            
            slide_id = response.get('replies')[0].get('createSlide').get('objectId')
            
            # Add delay between API calls
            time.sleep(1)
            
            # Get the placeholders on the slide
            presentation = self._execute_with_backoff(service.presentations().get(
                presentationId=presentation_id
            ))
            
            # Find the slide we just created
            slide = None
            for s in presentation.get('slides', []):
                if s.get('objectId') == slide_id:
                    slide = s
                    break
            
            if not slide:
                logger.error("Couldn't find the created slide.")
                return slide_id
            
            # Find title and body placeholders
            title_placeholder_id = None
            body_placeholder_id = None
            
            for element in slide.get('pageElements', []):
                shape = element.get('shape', {})
                placeholder = shape.get('placeholder', {})
                if placeholder.get('type') == 'TITLE':
                    title_placeholder_id = element.get('objectId')
                elif placeholder.get('type') == 'BODY':
                    body_placeholder_id = element.get('objectId')
            
            # Update title text if we found the placeholder
            requests = []
            if title_placeholder_id:
                requests.append({
                    'insertText': {
                        'objectId': title_placeholder_id,
                        'text': f'Question {question_number}'
                    }
                })
                
                # Update text style with blue color and bold
                requests.append({
                    'updateTextStyle': {
                        'objectId': title_placeholder_id,
                        'style': {
                            'bold': True,
                            'fontSize': {
                                'magnitude': self.FONT_SIZES['heading'],
                                'unit': 'PT'
                            },
                            'foregroundColor': {
                                'opaqueColor': {
                                    'rgbColor': self.COLORS['primary_blue']
                                }
                            }
                        },
                        'fields': 'bold,fontSize,foregroundColor'
                    }
                })
                
                # Center align the title
                requests.append({
                    'updateParagraphStyle': {
                        'objectId': title_placeholder_id,
                        'style': {
                            'alignment': 'CENTER'
                        },
                        'fields': 'alignment'
                    }
                })
            
            # Update body text if we found the placeholder
            if body_placeholder_id:
                # Replace any literal \n with actual newlines
                if question_text:
                    question_text = question_text.replace('\\n', '\n')
                else:
                    question_text = ""
                
                # First add the text
                requests.append({
                    'insertText': {
                        'objectId': body_placeholder_id,
                        'text': question_text
                    }
                })
                
                # Check if body contains bullet points (lines starting with - or *)
                if question_text and any(line.strip().startswith(('-', '*')) for line in question_text.split('\n')):
                    # Convert bullet points
                    requests.append({
                        'createParagraphBullets': {
                            'objectId': body_placeholder_id,
                            'textRange': {
                                'type': 'ALL'
                            },
                            'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE'
                        }
                    })
                    
                # Then update text style
                requests.append({
                    'updateTextStyle': {
                        'objectId': body_placeholder_id,
                        'style': {
                            'fontSize': {
                                'magnitude': self.FONT_SIZES['body'],
                                'unit': 'PT'
                            }
                        },
                        'fields': 'fontSize'
                    }
                })
                
                # Lastly, update paragraph styling
                requests.append({
                    'updateParagraphStyle': {
                        'objectId': body_placeholder_id,
                        'style': {
                            'alignment': 'CENTER',
                            'spaceAbove': {
                                'magnitude': 20,  # Add 20pt space above the body text
                                'unit': 'PT'
                            }
                        },
                        'fields': 'alignment,spaceAbove'
                    }
                })
            
            if requests:
                self._execute_with_backoff(service.presentations().batchUpdate(
                    presentationId=presentation_id,
                    body={'requests': requests}
                ))
            
            return slide_id
        except Exception as e:
            logger.error(f"Error creating question slide: {str(e)}")
            raise
        
    def _create_answer_slide(self, service, drive_service, presentation_id, answer_number, answer_text):
        """Create a slide with an answer"""
        try:
            # First create a blank slide with TITLE_AND_BODY layout
            requests = [
                {
                    'createSlide': {
                        'slideLayoutReference': {
                            'predefinedLayout': 'TITLE_AND_BODY'
                        }
                    }
                }
            ]
            
            response = self._execute_with_backoff(service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': requests}
            ))
            
            slide_id = response.get('replies')[0].get('createSlide').get('objectId')
            
            # Add delay between API calls
            time.sleep(1)
            
            # Get the slide to find the placeholder IDs
            presentation = self._execute_with_backoff(service.presentations().get(
                presentationId=presentation_id
            ))
            
            # Find the created slide and its placeholders
            title_placeholder_id = None
            body_placeholder_id = None
            
            for slide in presentation.get('slides', []):
                if slide.get('objectId') == slide_id:
                    for element in slide.get('pageElements', []):
                        shape = element.get('shape', {})
                        placeholder = shape.get('placeholder', {})
                        if placeholder.get('type') == 'TITLE':
                            title_placeholder_id = element.get('objectId')
                        elif placeholder.get('type') == 'BODY':
                            body_placeholder_id = element.get('objectId')
            
            # Set the title if we found the title placeholder
            requests = []
            if title_placeholder_id:
                requests.append({
                    'insertText': {
                        'objectId': title_placeholder_id,
                        'text': f'Answer {answer_number}'
                    }
                })
                
                # Style the title
                requests.append({
                    'updateTextStyle': {
                        'objectId': title_placeholder_id,
                        'style': {
                            'bold': True,
                            'fontSize': {
                                'magnitude': self.FONT_SIZES['heading'],
                                'unit': 'PT'
                            },
                            'foregroundColor': {
                                'opaqueColor': {
                                    'rgbColor': self.COLORS['primary_blue']
                                }
                            }
                        },
                        'fields': 'bold,fontSize,foregroundColor'
                    }
                })
                
                # Center align the title
                requests.append({
                    'updateParagraphStyle': {
                        'objectId': title_placeholder_id,
                        'style': {
                            'alignment': 'CENTER'
                        },
                        'fields': 'alignment'
                    }
                })
            
            if answer_text is None:
                answer_text = ""
                
            # Check if answer has math formulas
            if answer_text and self._contains_math_formula(answer_text):
                # If we have LaTeX, we'll try to render it as an image
                try:
                    image_data = self._render_latex_to_image(answer_text)
                    if image_data:
                        # Upload image to Drive
                        file_metadata = {
                            'name': f'latex_formula_{slide_id}.png',
                            'mimeType': 'image/png'
                        }
                        
                        media = MediaIoBaseUpload(image_data, mimetype='image/png')
                        file = self._execute_with_backoff(drive_service.files().create(
                            body=file_metadata,
                            media_body=media,
                            fields='id'
                        ))
                        
                        image_file_id = file.get('id')
                        
                        # Make the file accessible to anyone with the link
                        self._execute_with_backoff(drive_service.permissions().create(
                            fileId=image_file_id,
                            body={'type': 'anyone', 'role': 'reader'},
                            fields='id'
                        ))
                        
                        # Get the slide dimensions
                        slide_width = 720  # Default Google Slides width
                        slide_height = 405  # Default Google Slides height
                        
                        # Calculate image dimensions
                        image_width = 680  # Almost full width
                        image_height = 300  # Reasonable height for formula
                        
                        # Center the image on the slide
                        x_position = (slide_width - image_width) / 2
                        y_position = 200  # Position below title
                        
                        # Add image to slide request
                        requests.append({
                            'createImage': {
                                'url': f'https://drive.google.com/uc?id={image_file_id}',
                                'elementProperties': {
                                    'pageObjectId': slide_id,
                                    'size': {
                                        'width': {'magnitude': image_width, 'unit': 'PT'},
                                        'height': {'magnitude': image_height, 'unit': 'PT'}
                                    },
                                    'transform': {
                                        'scaleX': 1,
                                        'scaleY': 1,
                                        'translateX': x_position,
                                        'translateY': y_position,
                                        'unit': 'PT'
                                    }
                                }
                            }
                        })
                except Exception as e:
                    logger.error(f"Error rendering LaTeX: {e}")
                    # Fall back to text if LaTeX rendering fails
                    if body_placeholder_id:
                        # Replace any literal \n with actual newlines
                        answer_text = answer_text.replace('\\n', '\n')
                        
                        requests.append({
                            'insertText': {
                                'objectId': body_placeholder_id,
                                'text': answer_text
                            }
                        })
                        
                        # Style the text
                        requests.append({
                            'updateTextStyle': {
                                'objectId': body_placeholder_id,
                                'style': {
                                    'fontSize': {
                                        'magnitude': self.FONT_SIZES['body'],
                                        'unit': 'PT'
                                    }
                                },
                                'fields': 'fontSize'
                            }
                        })
            else:
                # Just regular text, no LaTeX
                if body_placeholder_id:
                    # Replace any literal \n with actual newlines
                    if answer_text:
                        answer_text = answer_text.replace('\\n', '\n')
                    
                    requests.append({
                        'insertText': {
                            'objectId': body_placeholder_id,
                            'text': answer_text
                        }
                    })
                    
                    # Style the text
                    requests.append({
                        'updateTextStyle': {
                            'objectId': body_placeholder_id,
                            'style': {
                                'fontSize': {
                                    'magnitude': self.FONT_SIZES['body'],
                                    'unit': 'PT'
                                }
                            },
                            'fields': 'fontSize'
                        }
                    })
                    
                    # Check if body contains bullet points
                    if answer_text and any(line.strip().startswith(('-', '*')) for line in answer_text.split('\n')):
                        # Convert bullet points
                        requests.append({
                            'createParagraphBullets': {
                                'objectId': body_placeholder_id,
                                'textRange': {
                                    'type': 'ALL'
                                },
                                'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE'
                            }
                        })
                    else:
                        # Center align if not a bullet list
                        requests.append({
                            'updateParagraphStyle': {
                                'objectId': body_placeholder_id,
                                'style': {
                                    'alignment': 'CENTER'
                                },
                                'fields': 'alignment'
                            }
                        })
            
            # Execute all requests
            if requests:
                self._execute_with_backoff(service.presentations().batchUpdate(
                    presentationId=presentation_id,
                    body={'requests': requests}
                ))
            
            return slide_id
        except Exception as e:
            logger.error(f"Error creating answer slide: {str(e)}")
            raise
        
    def _create_transition_slides(self, service, drive_service, presentation_id, text, font_size=32):
        """Create transition slides with improved formatting"""
        try:
            # Create a blank slide
            requests = [
                {
                    'createSlide': {
                        'slideLayoutReference': {
                            'predefinedLayout': 'BLANK'
                        }
                    }
                }
            ]
            
            response = self._execute_with_backoff(service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': requests}
            ))
            
            slide_id = response.get('replies')[0].get('createSlide').get('objectId')
            
            # Add delay between API calls
            time.sleep(1)
            
            # Create a text box that takes up more of the slide
            textbox_id = f'textbox_{slide_id}'
            requests = [
                {
                    'createShape': {
                        'objectId': textbox_id,
                        'shapeType': 'TEXT_BOX',
                        'elementProperties': {
                            'pageObjectId': slide_id,
                            'size': {
                                'width': {'magnitude': 650, 'unit': 'PT'},
                                'height': {'magnitude': 350, 'unit': 'PT'}
                            },
                            'transform': {
                                'scaleX': 1,
                                'scaleY': 1,
                                'translateX': 85,  # More centered
                                'translateY': 100,
                                'unit': 'PT'
                            }
                        }
                    }
                }
            ]
            
            self._execute_with_backoff(service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': requests}
            ))
            
            # Add delay between API calls
            time.sleep(1)
            
            # Process any literal \n characters to actual line breaks
            if text:
                text = text.replace('\\n', '\n')
                
                # Remove pagination markers and clean text
                formatted_text = text.replace(" (1/2)", "").replace(" (2/2)", "")
                formatted_text = formatted_text.replace("(1/2)", "").replace("(2/2)", "")
            else:
                formatted_text = ""
            
            # Insert text
            text_style_request = {
                'insertText': {
                    'objectId': textbox_id,
                    'text': formatted_text
                }
            }
            
            self._execute_with_backoff(service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': [text_style_request]}
            ))
            
            # Format text with proper font size and color
            style_request = {
                'updateTextStyle': {
                    'objectId': textbox_id,
                    'style': {
                        'fontSize': {
                            'magnitude': font_size,
                            'unit': 'PT'
                        },
                        'foregroundColor': {
                            'opaqueColor': {
                                'rgbColor': self.COLORS['primary_blue']
                            }
                        }
                    },
                    'fields': 'fontSize,foregroundColor'
                }
            }
            
            self._execute_with_backoff(service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': [style_request]}
            ))
            
            # Check if text contains bullet points and format appropriately
            if formatted_text and any(line.strip().startswith(('-', '*')) for line in formatted_text.split('\n')):
                # Apply bullet styling
                bullets_request = {
                    'createParagraphBullets': {
                        'objectId': textbox_id,
                        'textRange': {
                            'type': 'ALL'
                        },
                        'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE'
                    }
                }
                
                self._execute_with_backoff(service.presentations().batchUpdate(
                    presentationId=presentation_id,
                    body={'requests': [bullets_request]}
                ))
            else:
                # Center align text if not bullets
                paragraph_style_request = {
                    'updateParagraphStyle': {
                        'objectId': textbox_id,
                        'style': {
                            'alignment': 'CENTER',
                            'lineSpacing': 180,
                            'spaceAbove': {
                                'magnitude': 10,
                                'unit': 'PT'
                            },
                            'spaceBelow': {
                                'magnitude': 10,
                                'unit': 'PT'
                            }
                        },
                        'fields': 'alignment,lineSpacing,spaceAbove,spaceBelow'
                    }
                }
                
                self._execute_with_backoff(service.presentations().batchUpdate(
                    presentationId=presentation_id,
                    body={'requests': [paragraph_style_request]}
                ))
            
            return slide_id
        except Exception as e:
            logger.error(f"Error creating transition slide: {str(e)}")
            raise
        
    def _create_basic_slide(self, service, presentation_id, title, body=None):
        """Creates a basic slide with a title and optional body text."""
        try:
            # First create the slide with the TITLE_AND_BODY layout
            requests = [{'createSlide': {'slideLayoutReference': {'predefinedLayout': 'TITLE_AND_BODY'}}}]
            response = self._execute_with_backoff(service.presentations().batchUpdate(
                presentationId=presentation_id, 
                body={'requests': requests}
            ))
            
            slide_id = response['replies'][0]['createSlide']['objectId']
            
            # Get the slide to find the placeholder IDs
            slide_response = self._execute_with_backoff(service.presentations().get(
                presentationId=presentation_id
            ))
            
            # Find the created slide and its placeholders
            title_placeholder_id = None
            body_placeholder_id = None
            
            for slide in slide_response.get('slides', []):
                if slide.get('objectId') == slide_id:
                    for element in slide.get('pageElements', []):
                        shape = element.get('shape', {})
                        placeholder = shape.get('placeholder', {})
                        if placeholder.get('type') == 'TITLE':
                            title_placeholder_id = element.get('objectId')
                        elif placeholder.get('type') == 'BODY':
                            body_placeholder_id = element.get('objectId')
            
            # Prepare requests for inserting text
            text_requests = []
            
            # Process any literal \n characters to actual line breaks
            if title:
                title = title.replace('\\n', '\n')
            else:
                title = ""
            
            if body:
                body = body.replace('\\n', '\n')
            
            # Insert title text if we found the title placeholder
            if title_placeholder_id and title:
                text_requests.append({
                    'insertText': {
                        'objectId': title_placeholder_id,
                        'text': title
                    }
                })
                
                # Style the title
                text_requests.append({
                    'updateTextStyle': {
                        'objectId': title_placeholder_id,
                        'style': {
                            'fontSize': {
                                'magnitude': self.FONT_SIZES['heading'],
                                'unit': 'PT'
                            },
                            'foregroundColor': {
                                'opaqueColor': {
                                    'rgbColor': self.COLORS['primary_blue']
                                }
                            },
                            'bold': True
                        },
                        'fields': 'fontSize,foregroundColor,bold'
                    }
                })
                
                # Center the title
                text_requests.append({
                    'updateParagraphStyle': {
                        'objectId': title_placeholder_id,
                        'style': {
                            'alignment': 'CENTER'
                        },
                        'fields': 'alignment'
                    }
                })
            
            # Insert body text if we found the body placeholder and body is provided
            if body_placeholder_id and body:
                text_requests.append({
                    'insertText': {
                        'objectId': body_placeholder_id,
                        'text': body
                    }
                })
                
                # Style the body text
                text_requests.append({
                    'updateTextStyle': {
                        'objectId': body_placeholder_id,
                        'style': {
                            'fontSize': {
                                'magnitude': self.FONT_SIZES['body'],
                                'unit': 'PT'
                            }
                        },
                        'fields': , 
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
    
    def _check_and_resize_image(self, image_data, max_size_bytes=2097152, max_width=1500, max_height=1000):
        """Resizes image if it exceeds size limit or dimensions."""
        try:
            from PIL import Image
            
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
        except Exception as e:
            logger.error(f"Error resizing image: {e}")
            # Return original if resizing fails
            image_data.seek(0)
            return image_data'bold,fontSize,foregroundColor'
                    }
                })
                
                # Center align the title
                requests.append({
                    'updateParagraphStyle': {
                        'objectId': title_placeholder_id,
                        'style': {
                            'alignment': 'CENTER'
                        },
                        'fields': 'alignment'
                    }
                })
            
            # Update subtitle text if we found the placeholder and subtitle is provided
            if subtitle_placeholder_id and subtitle:
                requests.append({
                    'insertText': {
                        'objectId': subtitle_placeholder_id,
                        'text': subtitle
                    }
                })
                
                # Update subtitle style
                requests.append({
                    'updateTextStyle': {
                        'objectId': subtitle_placeholder_id,
                        'style': {
                            'fontSize': {
                                'magnitude': self.FONT_SIZES['subtitle'],
                                'unit': 'PT'
                            }
                        },
                        'fields': 'fontSize'
                    }
                })
                
                # Center align the subtitle
                requests.append({
                    'updateParagraphStyle': {
                        'objectId': subtitle_placeholder_id,
                        'style': {
                            'alignment': 'CENTER'
                        },
                        'fields': 'alignment'
                    }
                })
            
            if requests:
                self._execute_with_backoff(service.presentations().batchUpdate(
                    presentationId=presentation_id,
                    body={'requests': requests}
                ))
            
            return slide_id
        except Exception as e:
            logger.error(f"Error creating title slide: {str(e)}")
            raise
        
    def _create_question_slide(self, service, drive_service, presentation_id, question_number, question_text):
        """Create a slide with a question"""
        try:
            # First create a blank slide with TITLE_AND_BODY layout
            requests = [
                {
                    'createSlide': {
                        'slideLayoutReference': {
                            'predefinedLayout': 'TITLE_AND_BODY'
                        }
                    }
                }
            ]
            
            response = self._execute_with_backoff(service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': requests}
            ))
            
            slide_id = response.get('replies')[0].get('createSlide').get('objectId')
            
            # Add delay between API calls
            time.sleep(1)
            
            # Get the placeholders on the slide
            presentation = self._execute_with_backoff(service.presentations().get(
                presentationId=presentation_id
            ))
            
            # Find the slide we just created
            slide = None
            for s in presentation.get('slides', []):
                if s.get('objectId') == slide_id:
                    slide = s
                    break
            
            if not slide:
                logger.error("Couldn't find the created slide.")
                return slide_id
            
            # Find title and body placeholders
            title_placeholder_id = None
            body_placeholder_id = None
            
            for element in slide.get('pageElements', []):
                shape = element.get('shape', {})
                placeholder = shape.get('placeholder', {})
                if placeholder.get('type') == 'TITLE':
                    title_placeholder_id = element.get('objectId')
                elif placeholder.get('type') == 'BODY':
                    body_placeholder_id = element.get('objectId')
            
            # Update title text if we found the placeholder
            requests = []
            if title_placeholder_id:
                requests.append({
                    'insertText': {
                        'objectId': title_placeholder_id,
                        'text': f'Question {question_number}'
                    }
                })
                
                # Update text style with blue color and bold
                requests.append({
                    'updateTextStyle': {
                        'objectId': title_placeholder_id,
                        'style': {
                            'bold': True,
                            'fontSize': {
                                'magnitude': self.FONT_SIZES['heading'],
                                'unit': 'PT'
                            },
                            'foregroundColor': {
                                'opaqueColor': {
                                    'rgbColor': self.COLORS['primary_blue']
                                }
                            }
                        },
                        'fields': 'bold,fontSize,foregroundColor'
                    }
                })
                
                # Center align the title
                requests.append({
                    'updateParagraphStyle': {
                        'objectId': title_placeholder_id,
                        'style': {
                            'alignment': 'CENTER'
                        },
                        'fields': 'alignment'
                    }
                })
            
            # Update body text if we found the placeholder
            if body_placeholder_id:
                # Replace any literal \n with actual newlines
                if question_text:
                    question_text = question_text.replace('\\n', '\n')
                else:
                    question_text = ""
                
                # First add the text
                requests.append({
                    'insertText': {
                        'objectId': body_placeholder_id,
                        'text': question_text
                    }
                })
                
                # Check if body contains bullet points (lines starting with - or *)
                if question_text and any(line.strip().startswith(('-', '*')) for line in question_text.split('\n')):
                    # Convert bullet points
                    requests.append({
                        'createParagraphBullets': {
                            'objectId': body_placeholder_id,
                            'textRange': {
                                'type': 'ALL'
                            },
                            'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE'
                        }
                    })
                    
                # Then update text style
                requests.append({
                    'updateTextStyle': {
                        'objectId': body_placeholder_id,
                        'style': {
                            'fontSize': {
                                'magnitude': self.FONT_SIZES['body'],
                                'unit': 'PT'
                            }
                        },
                        'fields': 'fontSize'
                    }
                })
                
                # Lastly, update paragraph styling
                requests.append({
                    'updateParagraphStyle': {
                        'objectId': body_placeholder_id,
                        'style': {
                            'alignment': 'CENTER',
                            'spaceAbove': {
                                'magnitude': 20,  # Add 20pt space above the body text
                                'unit': 'PT'
                            }
                        },
                        'fields': 'alignment,spaceAbove'
                    }
                })
            
            if requests:
                self._execute_with_backoff(service.presentations().batchUpdate(
                    presentationId=presentation_id,
                    body={'requests': requests}
                ))
            
            return slide_id
        except Exception as e:
            logger.error(f"Error creating question slide: {str(e)}")
            raise
        
    def _create_answer_slide(self, service, drive_service, presentation_id, answer_number, answer_text):
        """Create a slide with an answer"""
        try:
            # First create a blank slide with TITLE_AND_BODY layout
            requests = [
                {
                    'createSlide': {
                        'slideLayoutReference': {
                            'predefinedLayout': 'TITLE_AND_BODY'
                        }
                    }
                }
            ]
            
            response = self._execute_with_backoff(service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': requests}
            ))
            
            slide_id = response.get('replies')[0].get('createSlide').get('objectId')
            
            # Add delay between API calls
            time.sleep(1)
            
            # Get the slide to find the placeholder IDs
            presentation = self._execute_with_backoff(service.presentations().get(
                presentationId=presentation_id
            ))
            
            # Find the created slide and its placeholders
            title_placeholder_id = None
            body_placeholder_id = None
            
            for slide in presentation.get('slides', []):
                if slide.get('objectId') == slide_id:
                    for element in slide.get('pageElements', []):
                        shape = element.get('shape', {})
                        placeholder = shape.get('placeholder', {})
                        if placeholder.get('type') == 'TITLE':
                            title_placeholder_id = element.get('objectId')
                        elif placeholder.get('type') == 'BODY':
                            body_placeholder_id = element.get('objectId')
            
            # Set the title if we found the title placeholder
            requests = []
            if title_placeholder_id:
                requests.append({
                    'insertText': {
                        'objectId': title_placeholder_id,
                        'text': f'Answer {answer_number}'
                    }
                })
                
                # Style the title
                requests.append({
                    'updateTextStyle': {
                        'objectId': title_placeholder_id,
                        'style': {
                            'bold': True,
                            'fontSize': {
                                'magnitude': self.FONT_SIZES['heading'],
                                'unit': 'PT'
                            },
                            'foregroundColor': {
                                'opaqueColor': {
                                    'rgbColor': self.COLORS['primary_blue']
                                }
                            }
                        },
                        'fields': 'bold,fontSize,foregroundColor'
                    }
                })
                
                # Center align the title
                requests.append({
                    'updateParagraphStyle': {
                        'objectId': title_placeholder_id,
                        'style': {
                            'alignment': 'CENTER'
                        },
                        'fields': 'alignment'
                    }
                })
            
            if answer_text is None:
                answer_text = ""
                
            # Check if answer has math formulas
            if answer_text and self._contains_math_formula(answer_text):
                # If we have LaTeX, we'll try to render it as an image
                try:
                    image_data = self._render_latex_to_image(answer_text)
                    if image_data:
                        # Upload image to Drive
                        file_metadata = {
                            'name': f'latex_formula_{slide_id}.png',
                            'mimeType': 'image/png'
                        }
                        
                        media = MediaIoBaseUpload(image_data, mimetype='image/png')
                        file = self._execute_with_backoff(drive_service.files().create(
                            body=file_metadata,
                            media_body=media,
                            fields='id'
                        ))
                        
                        image_file_id = file.get('id')
                        
                        # Make the file accessible to anyone with the link
                        self._execute_with_backoff(drive_service.permissions().create(
                            fileId=image_file_id,
                            body={'type': 'anyone', 'role': 'reader'},
                            fields='id'
                        ))
                        
                        # Get the slide dimensions
                        slide_width = 720  # Default Google Slides width
                        slide_height = 405  # Default Google Slides height
                        
                        # Calculate image dimensions
                        image_width = 680  # Almost full width
                        image_height = 300  # Reasonable height for formula
                        
                        # Center the image on the slide
                        x_position = (slide_width - image_width) / 2
                        y_position = 200  # Position below title
                        
                        # Add image to slide request
                        requests.append({
                            'createImage': {
                                'url': f'https://drive.google.com/uc?id={image_file_id}',
                                'elementProperties': {
                                    'pageObjectId': slide_id,
                                    'size': {
                                        'width': {'magnitude': image_width, 'unit': 'PT'},
                                        'height': {'magnitude': image_height, 'unit': 'PT'}
                                    },
                                    'transform': {
                                        'scaleX': 1,
                                        'scaleY': 1,
                                        'translateX': x_position,
                                        'translateY': y_position,
                                        'unit': 'PT'
                                    }
                                }
                            }
                        })
                except Exception as e:
                    logger.error(f"Error rendering LaTeX: {e}")
                    # Fall back to text if LaTeX rendering fails
                    if body_placeholder_id:
                        # Replace any literal \n with actual newlines
                        answer_text = answer_text.replace('\\n', '\n')
                        
                        requests.append({
                            'insertText': {
                                'objectId': body_placeholder_id,
                                'text': answer_text
                            }
                        })
                        
                        # Style the text
                        requests.append({
                            'updateTextStyle': {
                                'objectId': body_placeholder_id,
                                'style': {
                                    'fontSize': {
                                        'magnitude': self.FONT_SIZES['body'],
                                        'unit': 'PT'
                                    }
                                },
                                'fields': 'fontSize'
                            }
                        })
            else:
                # Just regular text, no LaTeX
                if body_placeholder_id:
                    # Replace any literal \n with actual newlines
                    if answer_text:
                        answer_text = answer_text.replace('\\n', '\n')
                    
                    requests.append({
                        'insertText': {
                            'objectId': body_placeholder_id,
                            'text': answer_text
                        }
                    })
                    
                    # Style the text
                    requests.append({
                        'updateTextStyle': {
                            'objectId': body_placeholder_id,
                            'style': {
                                'fontSize': {
                                    'magnitude': self.FONT_SIZES['body'],
                                    'unit': 'PT'
                                }
                            },
                            'fields': 'fontSize'
                        }
                    })
                    
                    # Check if body contains bullet points
                    if answer_text and any(line.strip().startswith(('-', '*')) for line in answer_text.split('\n')):
                        # Convert bullet points
                        requests.append({
                            'createParagraphBullets': {
                                'objectId': body_placeholder_id,
                                'textRange': {
                                    'type': 'ALL'
                                },
                                'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE'
                            }
                        })
                    else:
                        # Center align if not a bullet list
                        requests.append({
                            'updateParagraphStyle': {
                                'objectId': body_placeholder_id,
                                'style': {
                                    'alignment': 'CENTER'
                                },
                                'fields': 'alignment'
                            }
                        })
            
            # Execute all requests
            if requests:
                self._execute_with_backoff(service.presentations().batchUpdate(
                    presentationId=presentation_id,
                    body={'requests': requests}
                ))
            
            return slide_id
        except Exception as e:
            logger.error(f"Error creating answer slide: {str(e)}")
            raise
        
    def _create_transition_slides(self, service, drive_service, presentation_id, text, font_size=32):
        """Create transition slides with improved formatting"""
        try:
            # Create a blank slide
            requests = [
                {
                    'createSlide': {
                        'slideLayoutReference': {
                            'predefinedLayout': 'BLANK'
                        }
                    }
                }
            ]
            
            response = self._execute_with_backoff(service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': requests}
            ))
            
            slide_id = response.get('replies')[0].get('createSlide').get('objectId')
            
            # Add delay between API calls
            time.sleep(1)
            
            # Create a text box that takes up more of the slide
            textbox_id = f'textbox_{slide_id}'
            requests = [
                {
                    'createShape': {
                        'objectId': textbox_id,
                        'shapeType': 'TEXT_BOX',
                        'elementProperties': {
                            'pageObjectId': slide_id,
                            'size': {
                                'width': {'magnitude': 650, 'unit': 'PT'},
                                'height': {'magnitude': 350, 'unit': 'PT'}
                            },
                            'transform': {
                                'scaleX': 1,
                                'scaleY': 1,
                                'translateX': 85,  # More centered
                                'translateY': 100,
                                'unit': 'PT'
                            }
                        }
                    }
                }
            ]
            
            self._execute_with_backoff(service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': requests}
            ))
            
            # Add delay between API calls
            time.sleep(1)
            
            # Process any literal \n characters to actual line breaks
            if text:
                text = text.replace('\\n', '\n')
                
                # Remove pagination markers and clean text
                formatted_text = text.replace(" (1/2)", "").replace(" (2/2)", "")
                formatted_text = formatted_text.replace("(1/2)", "").replace("(2/2)", "")
            else:
                formatted_text = ""
            
            # Insert text
            text_style_request = {
                'insertText': {
                    'objectId': textbox_id,
                    'text': formatted_text
                }
            }
            
            self._execute_with_backoff(service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': [text_style_request]}
            ))
            
            # Format text with proper font size and color
            style_request = {
                'updateTextStyle': {
                    'objectId': textbox_id,
                    'style': {
                        'fontSize': {
                            'magnitude': font_size,
                            'unit': 'PT'
                        },
                        'foregroundColor': {
                            'opaqueColor': {
                                'rgbColor': self.COLORS['primary_blue']
                            }
                        }
                    },
                    'fields': 'fontSize,foregroundColor'
                }
            }
            
            self._execute_with_backoff(service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': [style_request]}
            ))
            
            # Check if text contains bullet points and format appropriately
            if formatted_text and any(line.strip().startswith(('-', '*')) for line in formatted_text.split('\n')):
                # Apply bullet styling
                bullets_request = {
                    'createParagraphBullets': {
                        'objectId': textbox_id,
                        'textRange': {
                            'type': 'ALL'
                        },
                        'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE'
                    }
                }
                
                self._execute_with_backoff(service.presentations().batchUpdate(
                    presentationId=presentation_id,
                    body={'requests': [bullets_request]}
                ))
            else:
                # Center align text if not bullets
                paragraph_style_request = {
                    'updateParagraphStyle': {
                        'objectId': textbox_id,
                        'style': {
                            'alignment': 'CENTER',
                            'lineSpacing': 180,
                            'spaceAbove': {
                                'magnitude': 10,
                                'unit': 'PT'
                            },
                            'spaceBelow': {
                                'magnitude': 10,
                                'unit': 'PT'
                            }
                        },
                        'fields': 'alignment,lineSpacing,spaceAbove,spaceBelow'
                    }
                }
                
                self._execute_with_backoff(service.presentations().batchUpdate(
                    presentationId=presentation_id,
                    body={'requests': [paragraph_style_request]}
                ))
            
            return slide_id
        except Exception as e:
            logger.error(f"Error creating transition slide: {str(e)}")
            raise
        
    def _create_basic_slide(self, service, presentation_id, title, body=None):
        """Creates a basic slide with a title and optional body text."""
        try:
            # First create the slide with the TITLE_AND_BODY layout
            requests = [{'createSlide': {'slideLayoutReference': {'predefinedLayout': 'TITLE_AND_BODY'}}}]
            response = self._execute_with_backoff(service.presentations().batchUpdate(
                presentationId=presentation_id, 
                body={'requests': requests}
            ))
            
            slide_id = response['replies'][0]['createSlide']['objectId']
            
            # Get the slide to find the placeholder IDs
            slide_response = self._execute_with_backoff(service.presentations().get(
                presentationId=presentation_id
            ))
            
            # Find the created slide and its placeholders
            title_placeholder_id = None
            body_placeholder_id = None
            
            for slide in slide_response.get('slides', []):
                if slide.get('objectId') == slide_id:
                    for element in slide.get('pageElements', []):
                        shape = element.get('shape', {})
                        placeholder = shape.get('placeholder', {})
                        if placeholder.get('type') == 'TITLE':
                            title_placeholder_id = element.get('objectId')
                        elif placeholder.get('type') == 'BODY':
                            body_placeholder_id = element.get('objectId')
            
            # Prepare requests for inserting text
            text_requests = []
            
            # Process any literal \n characters to actual line breaks
            if title:
                title = title.replace('\\n', '\n')
            else:
                title = ""
            
            if body:
                body = body.replace('\\n', '\n')
            
            # Insert title text if we found the title placeholder
            if title_placeholder_id and title:
                text_requests.append({
                    'insertText': {
                        'objectId': title_placeholder_id,
                        'text': title
                    }
                })
                
                # Style the title
                text_requests.append({
                    'updateTextStyle': {
                        'objectId': title_placeholder_id,
                        'style': {
                            'fontSize': {
                                'magnitude': self.FONT_SIZES['heading'],
                                'unit': 'PT'
                            },
                            'foregroundColor': {
                                'opaqueColor': {
                                    'rgbColor': self.COLORS['primary_blue']
                                }
                            },
                            'bold': True
                        },
                        'fields': 'fontSize,foregroundColor,bold'
                    }
                })
                
                # Center the title
                text_requests.append({
                    'updateParagraphStyle': {
                        'objectId': title_placeholder_id,
                        'style': {
                            'alignment': 'CENTER'
                        },
                        'fields': 'alignment'
                    }
                })
            
            # Insert body text if we found the body placeholder and body is provided
            if body_placeholder_id and body:
                text_requests.append({
                    'insertText': {
                        'objectId': body_placeholder_id,
                        'text': body
                    }
                })
                
                # Style the body text
                text_requests.append({
                    'updateTextStyle': {
                        'objectId': body_placeholder_id,
                        'style': {
                            'fontSize': {
                                'magnitude': self.FONT_SIZES['body'],
                                'unit': 'PT'
                            }
                        },
                        'fields':