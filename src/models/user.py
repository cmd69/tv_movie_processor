"""
User model for authentication in the TV Movie Processor application.

This module provides a simple user model compatible with Flask-Login.
Since we're using environment variables for credentials rather than a database,
this is a memory-based implementation.
"""

from flask_login import UserMixin
from flask import current_app
from werkzeug.security import check_password_hash

class User(UserMixin):
    """
    User class for authentication with Flask-Login.
    
    This is a memory-based implementation since we're using environment variables
    for credentials rather than storing users in a database.
    
    Attributes:
        id (str): User ID (username)
        username (str): Username
        is_admin (bool): Whether the user is an admin
    """
    
    def __init__(self, id, username, is_admin=False):
        """
        Initialize a user.
        
        Args:
            id (str): User ID (username)
            username (str): Username
            is_admin (bool): Whether the user is an admin
        """
        self.id = id
        self.username = username
        self.is_admin = is_admin
    
    @classmethod
    def get(cls, id):
        """
        Get a user by ID.
        
        Since we only have one admin user from environment variables,
        this simply checks if the ID matches the admin username.
        
        Args:
            id (str): User ID to look up
            
        Returns:
            User: User instance if found, None otherwise
        """
        if id == current_app.config.get('ADMIN_USERNAME'):
            return cls(id, id, is_admin=True)
        return None
    
    @classmethod
    def authenticate(cls, username, password):
        """
        Authenticate a user with username and password.
        
        Args:
            username (str): Username to authenticate
            password (str): Password to verify
            
        Returns:
            User: User instance if authentication successful, None otherwise
        """
        if username != current_app.config.get('ADMIN_USERNAME'):
            return None
        
        if check_password_hash(current_app.config.get('ADMIN_PASSWORD_HASH'), password):
            return cls(username, username, is_admin=True)
        
        return None
