"""Initialize database with default users."""

from backend.database import SessionLocal
from backend.services.user_service import UserService


def init_db():
    """Create default admin and user accounts."""
    db = SessionLocal()
    user_service = UserService(db)
    
    try:
        # Create admin user
        try:
            admin = user_service.create_user(
                username="admin",
                password="admin123",
                email="admin@test.com",
                is_admin=True
            )
            print(f"✅ Created admin user: {admin.username}")
        except ValueError as e:
            # Admin already exists, update to admin role
            from backend.models import User
            admin = db.query(User).filter(User.username == "admin").first()
            if admin:
                admin.is_admin = True
                db.commit()
                print(f"✅ Updated admin user: {admin.username}")
            else:
                print(f"⚠️  Admin user creation failed: {e}")
        
        # Create regular user
        try:
            user = user_service.create_user(
                username="user",
                password="user123",
                email="user@test.com",
                is_admin=False
            )
            print(f"✅ Created regular user: {user.username}")
        except ValueError as e:
            print(f"ℹ️  Regular user already exists: {e}")
            
        print("\n🎉 Database initialization complete!")
        print("\nTest credentials:")
        print("  Admin:  admin / admin123")
        print("  User:   user / user123")
        
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
