"""
Authentication routes for the TV Movie Processor application.

This module provides routes for login, logout, and authentication.
"""

from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from src.models.user import User

# Create blueprint for authentication routes
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handle user login.
    
    GET: Display login form
    POST: Process login form submission
    
    Returns:
        Response: Rendered login template or redirect to index
    """
    # If user is already authenticated, redirect to index
    if current_user.is_authenticated:
        return redirect(url_for('serve', path=''))
    
    # Handle form submission
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = 'remember' in request.form
        
        # Validate credentials
        user = User.authenticate(username, password)
        
        if user:
            # Log in the user
            login_user(user, remember=remember)
            
            # Get the next page from the request or default to index
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('serve', path='')
                
            return redirect(next_page)
        else:
            # Authentication failed
            flash('Invalid username or password', 'danger')
    
    # Render login template
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    """
    Handle user logout.
    
    Returns:
        Response: Redirect to login page
    """
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('auth.login'))
