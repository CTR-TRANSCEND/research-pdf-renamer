from flask import Flask, request, g
from flask_login import LoginManager, current_user
from backend.config import config
from backend.database import db
from backend.models import User, Usage, SystemSettings
import os
import datetime

def create_app(config_name=None):
    # Get the absolute path to the project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(__name__,
                template_folder=os.path.join(project_root, 'frontend', 'templates'),
                static_folder=os.path.join(project_root, 'frontend', 'static'))

    # Load configuration
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    app.config.from_object(config[config_name])

    # Initialize extensions
    db.init_app(app)
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from backend.routes.main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from backend.routes.auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/api/auth')

    from backend.routes.upload import upload as upload_blueprint
    app.register_blueprint(upload_blueprint, url_prefix='/api')

    from backend.routes.admin import admin as admin_blueprint
    app.register_blueprint(admin_blueprint, url_prefix='/api/admin')

    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return {'error': 'Resource not found'}, 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return {'error': 'Internal server error'}, 500

    @app.errorhandler(413)
    def too_large(error):
        return {'error': 'File too large'}, 413

    # Register CLI commands
    from backend.cli import register_cli_commands
    register_cli_commands(app)

    # Create tables
    with app.app_context():
        db.create_all()

        # Run database migrations for existing tables
        _run_migrations(db)

        # Check admin setup (don't auto-create admin)
        from backend.utils.admin_setup import check_admin_on_startup
        check_admin_on_startup()

    return app

def _run_migrations(db):
    """Run manual migrations to add new columns to existing tables."""
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)

    # Check and add 'success' column to 'usage' table
    if 'usage' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('usage')]
        if 'success' not in columns:
            try:
                db.session.execute(text('ALTER TABLE usage ADD COLUMN success BOOLEAN DEFAULT 1'))
                db.session.commit()
                print("[Migration] Added 'success' column to usage table")
            except Exception as e:
                print(f"[Migration] Note: Could not add success column (may already exist): {e}")
                db.session.rollback()

    # Check and add columns to 'system_settings' table if needed
    if 'system_settings' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('system_settings')]
        # Add any new columns here as needed
        pass