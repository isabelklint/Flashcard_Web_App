# models/presentation.py
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Presentation(db.Model):
    """Model for storing presentation metadata"""
    __tablename__ = 'presentations'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    google_presentation_id = db.Column(db.String(100), unique=True, nullable=False)
    google_url = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.String(100), nullable=False, index=True)  # Google user ID
    
    def to_dict(self):
        """Convert model to dictionary for API responses"""
        return {
            'id': self.id,
            'title': self.title,
            'google_presentation_id': self.google_presentation_id,
            'google_url': self.google_url,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def create_from_google_data(cls, user_id, title, google_presentation_id, google_url):
        """Factory method to create a presentation from Google API response"""
        presentation = cls(
            title=title,
            google_presentation_id=google_presentation_id,
            google_url=google_url,
            user_id=user_id
        )
        db.session.add(presentation)
        db.session.commit()
        return presentation