"""Migration script to remove hardcoded admin credentials."""
import sys
import os
from backend.app import create_app
from backend.models import User, SystemSettings
from backend.database import db

def remove_hardcoded_admin():
    """Remove the hardcoded admin user if it exists."""
    app = create_app()

    with app.app_context():
        # Check for the hardcoded admin
        hardcoded_admin = User.query.filter_by(email='admin@example.com').first()

        if hardcoded_admin:
            print("⚠️  Found hardcoded admin user:")
            print(f"   Email: {hardcoded_admin.email}")
            print(f"   Name: {hardcoded_admin.name}")
            print(f"   ID: {hardcoded_admin.id}")

            # Check if there are other admins
            other_admins = User.query.filter(
                User.is_admin == True,
                User.id != hardcoded_admin.id
            ).all()

            if other_admins:
                print(f"\n✓ Found {len(other_admins)} other admin(s). Safe to remove hardcoded admin.")
                choice = input("\nRemove hardcoded admin? (y/N): ").strip().lower()

                if choice == 'y':
                    # Delete the hardcoded admin and their usage logs
                    from backend.models import Usage
                    Usage.query.filter_by(user_id=hardcoded_admin.id).delete()
                    db.session.delete(hardcoded_admin)
                    db.session.commit()
                    print("✓ Hardcoded admin removed successfully!")
                else:
                    print("✗ Hardcoded admin left unchanged.")
                    return False
            else:
                print("\n⚠️  WARNING: No other admins found!")
                print("You should create a new admin before removing the hardcoded one.")
                print("Run 'flask setup-admin' to create a new admin first.")

                # Ask if they want to proceed anyway
                choice = input("\nRemove anyway? (NOT RECOMMENDED) (y/N): ").strip().lower()
                if choice == 'y':
                    from backend.models import Usage
                    Usage.query.filter_by(user_id=hardcoded_admin.id).delete()
                    db.session.delete(hardcoded_admin)
                    db.session.commit()
                    print("✓ Hardcoded admin removed. WARNING: No admins remain!")
                else:
                    print("✗ Hardcoded admin left unchanged.")
                    return False
        else:
            print("✓ No hardcoded admin found. System is already secure.")
            return True

        return True

if __name__ == '__main__':
    if remove_hardcoded_admin():
        print("\n✅ Migration completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Migration not completed.")
        sys.exit(1)