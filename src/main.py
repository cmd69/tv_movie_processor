"""
Main entry point for the TV Movie Processor Flask application.

This module initializes the Flask app, configures the database,
sets up authentication, and registers all routes.
"""

import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, session, redirect, url_for
from flask_login import LoginManager, current_user
from werkzeug.security import generate_password_hash

# Import database configuration
from src.models.database import init_db
from src.models.user import User

# Import routes
from src.routes.processor import processor_bp
from src.routes.auth import auth_bp

def create_app():
    """
    Create and configure the Flask application.
    
    This function:
    1. Creates the Flask app
    2. Configures the secret key from environment
    3. Initializes the database
    4. Sets up authentication
    5. Registers all blueprints (routes)
    
    Returns:
        Flask: The configured Flask application
    """
    # Create Flask app
    app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
    
    # Configure secret key from environment or use default
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'asdf#FGSgvasgf$5$WGT')
    
    # Initialize database
    db, migrate = init_db(app)
    
    # Setup authentication
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    @login_manager.user_loader
    def load_user(user_id):
        """Load user by ID for Flask-Login"""
        return User.get(user_id)
    
    # Create admin user from environment variables
    with app.app_context():
        admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
        admin_password = os.environ.get('ADMIN_PASSWORD', 'password')
        
        # Store admin credentials in app config for login validation
        app.config['ADMIN_USERNAME'] = admin_username
        app.config['ADMIN_PASSWORD_HASH'] = generate_password_hash(admin_password)
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(processor_bp)
    
    # Configure media root from environment
    app.config['MEDIA_ROOT'] = os.environ.get('MEDIA_ROOT', '/mnt/nfs/media')
    
    # Serve static files and index.html
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        """
        Serve static files and the main index.html.
        
        This route handles:
        1. Serving specific static files when requested
        2. Falling back to index.html for all other routes (for SPA support)
        3. Redirecting to login if user is not authenticated
        
        Args:
            path (str): The requested path
            
        Returns:
            Response: The requested file or index.html
        """
        # Check if user is authenticated
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
            
        static_folder_path = app.static_folder
        if static_folder_path is None:
            return "Static folder not configured", 404

        if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
            return send_from_directory(static_folder_path, path)
        else:
            index_path = os.path.join(static_folder_path, 'index.html')
            if os.path.exists(index_path):
                return send_from_directory(static_folder_path, 'index.html')
            else:
                return "index.html not found", 404
    
    return app

# Create the application instance
app = create_app()

if __name__ == '__main__':
    # Run the application
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    app.run(host='0.0.0.0', port=port, debug=debug)
