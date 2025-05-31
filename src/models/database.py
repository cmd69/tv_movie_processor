"""
Database configuration and initialization for the TV Movie Processor application.

This module provides database setup functions and configuration options.
It supports both SQLite (for development) and other database backends via environment variables.
"""

import os
from flask_migrate import Migrate

from src.models.job import db, Job, JobResult

def init_db(app):
    """
    Initialize the database with the Flask application.
    
    This function configures the database URI based on environment variables,
    initializes the SQLAlchemy instance with the app, and sets up migrations.
    
    Args:
        app: Flask application instance
    
    Returns:
        tuple: (db, migrate) - The database and migration instances
    """
    # Get database configuration from environment variables with defaults
    db_type = os.environ.get('DB_TYPE', 'sqlite')
    
    if db_type == 'sqlite':
        # SQLite configuration (default for development)
        db_path = os.environ.get('DB_PATH', os.path.join(app.instance_path, 'tv_movie_processor.db'))
        
        # Ensure the instance folder exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    else:
        # MySQL/PostgreSQL configuration
        db_user = os.environ.get('DB_USERNAME', 'root')
        db_password = os.environ.get('DB_PASSWORD', 'password')
        db_host = os.environ.get('DB_HOST', 'localhost')
        db_port = os.environ.get('DB_PORT', '3306')
        db_name = os.environ.get('DB_NAME', 'tv_movie_processor')
        
        app.config['SQLALCHEMY_DATABASE_URI'] = f"{db_type}://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    # Disable modification tracking to improve performance
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize the database with the app
    db.init_app(app)
    
    # Setup Flask-Migrate
    migrate = Migrate(app, db)
    
    # Create tables if they don't exist
    with app.app_context():
        db.create_all()
    
    return db, migrate
