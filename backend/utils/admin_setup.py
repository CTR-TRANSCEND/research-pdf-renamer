"""Initial admin setup utilities."""
import os
import click
from backend.models import User, SystemSettings
from backend.database import db
from getpass import getpass
import sys

def check_admin_exists():
    """Check if any admin user exists in the system."""
    return User.query.filter_by(is_admin=True).first() is not None

def create_first_admin(email=None, password=None, name=None):
    """Create the first admin user."""
    if check_admin_exists():
        print("Admin user already exists. Skipping setup.")
        return False

    # Get admin details if not provided
    if not email:
        while True:
            email = input("Enter admin email: ").strip()
            if '@' in email and '.' in email:
                break
            print("Invalid email address. Please try again.")

    if not name:
        name = input("Enter admin name: ").strip()
        if not name:
            name = "Administrator"

    if not password:
        while True:
            password = getpass("Enter admin password: ")
            if len(password) < 8:
                print("Password must be at least 8 characters long.")
                continue

            confirm_password = getpass("Confirm admin password: ")
            if password != confirm_password:
                print("Passwords do not match. Please try again.")
                continue
            break

    # Create admin user
    admin = User(
        email=email,
        name=name,
        is_admin=True,
        is_approved=True,
        is_active=True
    )
    admin.set_password(password)

    db.session.add(admin)
    db.session.commit()

    # Mark setup as complete
    SystemSettings.set_setting('admin_setup_complete', 'true', user_id=admin.id)

    print(f"\n✓ Admin user created successfully!")
    print(f"  Email: {email}")
    print(f"  Name: {name}")
    print(f"\nPlease save these credentials securely.")
    print(f"You can now log in to the admin panel at: /admin\n")

    return True

def require_admin_setup():
    """Check if admin setup is required and prompt if needed."""
    # Check if setup is already complete
    setup_complete = SystemSettings.get_setting('admin_setup_complete', 'false')
    if setup_complete == 'true':
        return

    # Check if admin user exists
    if check_admin_exists():
        SystemSettings.set_setting('admin_setup_complete', 'true')
        return

    print("\n" + "="*60)
    print("ADMIN SETUP REQUIRED")
    print("="*60)
    print("\nNo admin user found. Let's create the first administrator.")
    print("This user will have full access to the system.\n")

    try:
        create_first_admin()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled. The application will not function without an admin.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError during admin setup: {e}")
        sys.exit(1)

@click.command()
def setup_admin():
    """Setup admin user command."""
    create_first_admin()

def check_admin_on_startup():
    """Check admin status on application startup (non-interactive mode)."""
    if check_admin_exists():
        return

    # In production/non-interactive mode, don't auto-create admin
    if os.environ.get('FLASK_ENV') == 'production':
        print("\n⚠️  WARNING: No admin user found!")
        print("Please run 'python -m backend.utils.admin_setup' to create an admin user.")
        print("The application will run in limited mode until an admin is configured.\n")
        return

    # For development, show a helpful message
    print("\n⚠️  No admin user found!")
    print("Run 'flask setup-admin' to create an administrator account.")
    print("Or visit the application and follow the setup prompts.\n")