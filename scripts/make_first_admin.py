from app import create_app
from app.models import db, User

app = create_app()

with app.app_context():
    u = User.query.order_by(User.id.asc()).first()
    if not u:
        print("No users found")
    else:
        u.is_admin = True
        db.session.commit()
        print(f"Made user #{u.id} ({u.email}) admin")
