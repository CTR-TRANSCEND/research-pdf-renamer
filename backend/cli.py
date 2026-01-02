"""Flask CLI commands for the application."""
import click
from flask import current_app
from backend.utils.admin_setup import create_first_admin
from backend.database import db

@click.command()
@click.option('--email', help='Admin email address')
@click.option('--password', help='Admin password')
@click.option('--name', help='Admin name')
def setup_admin(email, password, name):
    """Setup the first admin user."""
    with current_app.app_context():
        create_first_admin(email, password, name)

@click.command()
def create_tables():
    """Create database tables."""
    with current_app.app_context():
        db.create_all()
        print("Tables created successfully.")

def register_cli_commands(app):
    """Register CLI commands with the Flask app."""
    app.cli.add_command(setup_admin)
    app.cli.add_command(create_tables)