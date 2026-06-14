import unittest

from flask import Flask, jsonify

from app.api.auth import auth_bp
from app.models import Novel, NovelUserPermission, PasswordSetupToken, User, db
from app.services.auth import install_auth_guards


class AuthPermissionsTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="test-secret",
            SQLALCHEMY_DATABASE_URI="sqlite://",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(self.app)
        self.app.register_blueprint(auth_bp, url_prefix="/api")

        @self.app.get("/api/admin/protected")
        def protected():
            return jsonify({"data": {"ok": True}})

        @self.app.get("/api/admin/novels/<int:novel_id>/protected")
        def protected_novel(novel_id):
            return jsonify({"data": {"novel_id": novel_id}})

        install_auth_guards(self.app)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.client = self.app.test_client()

        self.novel = Novel(title="Test Novel", original_filename="", file_type="txt")
        self.other_novel = Novel(title="Other Novel", original_filename="", file_type="txt")
        db.session.add_all([self.novel, self.other_novel])
        db.session.flush()

        self.superadmin = User(username="root", email="root@example.com", role="superadmin")
        self.superadmin.set_password("password123")
        self.editor = User(username="ed", email="ed@example.com", role="editor")
        self.editor.set_password("password123")
        self.public_user = User(username="reader", email="reader@example.com", role="user")
        self.public_user.set_password("password123")
        db.session.add_all([self.superadmin, self.editor, self.public_user])
        db.session.flush()
        db.session.add(
            NovelUserPermission(
                novel_id=self.novel.id,
                user_id=self.editor.id,
                can_edit=True,
                can_review=True,
                can_approve=False,
            )
        )
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def login(self, email):
        return self.client.post(
            "/api/auth/login",
            json={"email": email, "password": "password123"},
        )

    def test_login_me_and_logout(self):
        response = self.login("root@example.com")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["user"]["role"], "superadmin")

        response = self.client.get("/api/auth/me")
        self.assertEqual(response.get_json()["data"]["user"]["email"], "root@example.com")

        response = self.client.post("/api/auth/logout")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.client.get("/api/auth/me").get_json()["data"]["user"])

    def test_public_user_cannot_access_admin(self):
        self.login("reader@example.com")
        response = self.client.get("/api/admin/protected")
        self.assertEqual(response.status_code, 403)

    def test_editor_can_access_assigned_novel_only(self):
        self.login("ed@example.com")

        response = self.client.get(f"/api/admin/novels/{self.novel.id}/protected")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"/api/admin/novels/{self.other_novel.id}/protected")
        self.assertEqual(response.status_code, 403)

    def test_public_registration_creates_only_user_role(self):
        response = self.client.post(
            "/api/auth/register",
            json={
                "username": "new-admin",
                "email": "new-admin@example.com",
                "password": "password123",
                "role": "superadmin",
            },
        )
        self.assertEqual(response.status_code, 201)
        created = User.query.filter_by(email="new-admin@example.com").one()
        self.assertEqual(created.role, "user")

    def test_superadmin_creates_user_with_password_setup_link(self):
        self.login("root@example.com")

        response = self.client.post(
            "/api/admin/users",
            json={
                "username": "new-editor",
                "email": "new-editor@example.com",
                "role": "editor",
                "is_active": True,
            },
        )

        self.assertEqual(response.status_code, 201)
        body = response.get_json()["data"]
        self.assertIn("setup_token", body["password_setup"])
        created = User.query.filter_by(email="new-editor@example.com").one()
        self.assertTrue(created.must_set_password)
        self.assertIsNone(created.password_hash)

        login_response = self.client.post(
            "/api/auth/login",
            json={"email": "new-editor@example.com", "password": ""},
        )
        self.assertEqual(login_response.status_code, 400)

        setup_response = self.client.post(
            "/api/auth/set-password",
            json={
                "token": body["password_setup"]["setup_token"],
                "password": "password123",
                "confirm_password": "password123",
            },
        )
        self.assertEqual(setup_response.status_code, 200)
        self.assertFalse(created.must_set_password)

        reused_response = self.client.post(
            "/api/auth/set-password",
            json={
                "token": body["password_setup"]["setup_token"],
                "password": "different123",
                "confirm_password": "different123",
            },
        )
        self.assertEqual(reused_response.status_code, 404)

    def test_admin_user_api_rejects_superadmin_creation(self):
        self.login("root@example.com")

        response = self.client.post(
            "/api/admin/users",
            json={
                "username": "another-root",
                "email": "another-root@example.com",
                "role": "superadmin",
                "is_active": True,
            },
        )

        self.assertEqual(response.status_code, 400)

    def test_superadmin_can_generate_password_reset_link(self):
        self.login("root@example.com")

        response = self.client.post(f"/api/admin/users/{self.editor.id}/password-reset")
        self.assertEqual(response.status_code, 200)
        token_count = PasswordSetupToken.query.filter_by(user_id=self.editor.id).count()
        self.assertEqual(token_count, 1)
        self.assertTrue(db.session.get(User, self.editor.id).must_set_password)


if __name__ == "__main__":
    unittest.main()
