"""
Job Model for TV Movie Processor

This module defines the database model for storing job history.
Jobs represent processing tasks that have been executed by the application.
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

# Initialize SQLAlchemy instance - will be configured in main.py
db = SQLAlchemy()

class Job(db.Model):
    """
    Job model for storing processing task history.
    
    Attributes:
        id (int): Primary key for the job
        job_id (str): Unique identifier for the job (timestamp-based)
        mode (str): Processing mode ('movie' or 'tv')
        status (str): Current status of the job ('starting', 'processing', 'completed', 'failed')
        file_count (int): Number of files being processed
        progress (float): Progress percentage (0-100)
        start_time (datetime): When the job was started
        end_time (datetime): When the job was completed (or failed)
        error (str): Error message if the job failed
        created_at (datetime): When the job record was created
    """
    __tablename__ = 'jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.String(50), unique=True, nullable=False)
    mode = db.Column(db.String(10), nullable=False)  # 'movie' or 'tv'
    status = db.Column(db.String(20), nullable=False, default='starting')
    file_count = db.Column(db.Integer, default=0)
    progress = db.Column(db.Float, default=0)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    results = db.relationship('JobResult', backref='job', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        """
        Convert job to dictionary for JSON serialization
        
        Returns:
            dict: Dictionary representation of the job
        """
        return {
            'id': self.id,
            'job_id': self.job_id,
            'mode': self.mode,
            'status': self.status,
            'file_count': self.file_count,
            'progress': self.progress,
            'start_time': self.start_time.timestamp() if self.start_time else None,
            'end_time': self.end_time.timestamp() if self.end_time else None,
            'error': self.error,
            'created_at': self.created_at.timestamp(),
            'results': [result.to_dict() for result in self.results]
        }


class JobResult(db.Model):
    """
    JobResult model for storing individual file processing results.
    
    Attributes:
        id (int): Primary key for the result
        job_id (int): Foreign key to the parent job
        vo_file (str): Path to the original version file
        es_file (str): Path to the Spanish dubbed file
        output_file (str): Path to the output file (if successful)
        success (bool): Whether the processing was successful
        message (str): Status or error message
    """
    __tablename__ = 'job_results'
    
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False)
    vo_file = db.Column(db.String(255), nullable=False)
    es_file = db.Column(db.String(255), nullable=False)
    output_file = db.Column(db.String(255), nullable=True)
    success = db.Column(db.Boolean, default=False)
    message = db.Column(db.Text, nullable=True)
    
    def to_dict(self):
        """
        Convert job result to dictionary for JSON serialization
        
        Returns:
            dict: Dictionary representation of the job result
        """
        return {
            'id': self.id,
            'vo_file': self.vo_file,
            'es_file': self.es_file,
            'output_file': self.output_file,
            'success': self.success,
            'message': self.message
        }
