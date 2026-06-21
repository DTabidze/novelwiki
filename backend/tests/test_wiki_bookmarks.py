import unittest

from flask import Flask

from app.api.auth import auth_bp
from app.api.wiki import wiki_bp
from app.models import Character, Item, Novel, Skill, User, UserBookmark, db


class WikiBookmarksTest(unittest.TestCase):
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
        self.app.register_blueprint(wiki_bp, url_prefix="/api/wiki")
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.client = self.app.test_client()

        self.novel = Novel(
            title="I Shall Seal the Heavens",
            author="Er Gen",
            original_filename="",
            file_type="txt",
        )
        self.other_novel = Novel(
            title="Renegade Immortal",
            author="Er Gen",
            original_filename="",
            file_type="txt",
        )
        self.user = User(username="reader", email="reader@example.com", role=User.ROLE_USER)
        self.user.set_password("password123")
        db.session.add_all([self.novel, self.other_novel, self.user])
        db.session.flush()

        self.character = Character(
            novel_id=self.novel.id,
            name="Meng Hao",
            review_status="approved",
        )
        self.pending_character = Character(
            novel_id=self.novel.id,
            name="Pending Character",
            review_status="pending",
        )
        self.skill = Skill(
            novel_id=self.novel.id,
            name="Cold Wind Finger",
            category="Technique",
            review_status="approved",
        )
        self.item = Item(
            novel_id=self.novel.id,
            name="Copper Mirror",
            category="Artifact",
            review_status="approved",
        )
        db.session.add_all([self.character, self.pending_character, self.skill, self.item])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def login(self):
        return self.client.post(
            "/api/auth/login",
            json={"email": "reader@example.com", "password": "password123"},
        )

    def test_bookmarks_require_authentication(self):
        response = self.client.get("/api/wiki/me/bookmarks")
        self.assertEqual(response.status_code, 401)

        response = self.client.post(
            "/api/wiki/me/bookmarks",
            json={"entity_type": "novel", "entity_id": self.novel.id},
        )
        self.assertEqual(response.status_code, 401)

    def test_user_can_add_list_and_remove_generic_bookmarks(self):
        self.login()

        targets = [
            ("novel", self.novel.id),
            ("character", self.character.id),
            ("skill", self.skill.id),
            ("item", self.item.id),
        ]

        for entity_type, entity_id in targets:
            response = self.client.post(
                "/api/wiki/me/bookmarks",
                json={"entity_type": entity_type, "entity_id": entity_id},
            )
            self.assertEqual(response.status_code, 201)
            body = response.get_json()["data"]
            self.assertTrue(body["created"])
            self.assertEqual(body["entity_type"], entity_type)
            self.assertEqual(body["entity_id"], entity_id)
            self.assertTrue(body["entity"]["is_bookmarked"])

        self.assertEqual(UserBookmark.query.count(), 4)

        response = self.client.get("/api/wiki/me/bookmarks")
        self.assertEqual(response.status_code, 200)
        bookmarks = response.get_json()["data"]
        bookmark_keys = {(bookmark["entity_type"], bookmark["entity_id"]) for bookmark in bookmarks}
        self.assertEqual(bookmark_keys, set(targets))

        response = self.client.delete(f"/api/wiki/me/bookmarks/skill/{self.skill.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(UserBookmark.query.count(), 3)

    def test_adding_same_bookmark_is_idempotent(self):
        self.login()

        first_response = self.client.post(f"/api/wiki/me/bookmarks/novel/{self.novel.id}")
        second_response = self.client.post(f"/api/wiki/me/bookmarks/novel/{self.novel.id}")

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 200)
        self.assertFalse(second_response.get_json()["data"]["created"])
        self.assertEqual(UserBookmark.query.count(), 1)

    def test_missing_or_unsupported_bookmark_targets_return_json_errors(self):
        self.login()

        response = self.client.post(
            "/api/wiki/me/bookmarks",
            json={"entity_type": "place", "entity_id": 999},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Unsupported bookmark type.")

        response = self.client.post(
            "/api/wiki/me/bookmarks",
            json={"entity_type": "character", "entity_id": self.pending_character.id},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "Bookmark target not found.")

    def test_public_payloads_mark_bookmarked_entities_for_current_user(self):
        self.login()
        self.client.post(f"/api/wiki/me/bookmarks/novel/{self.novel.id}")
        self.client.post(f"/api/wiki/me/bookmarks/character/{self.character.id}")
        self.client.post(f"/api/wiki/me/bookmarks/skill/{self.skill.id}")
        self.client.post(f"/api/wiki/me/bookmarks/item/{self.item.id}")

        response = self.client.get("/api/wiki/novels")
        self.assertEqual(response.status_code, 200)
        novels = response.get_json()["data"]
        bookmarked_by_id = {novel["id"]: novel["is_bookmarked"] for novel in novels}
        self.assertTrue(bookmarked_by_id[self.novel.id])
        self.assertFalse(bookmarked_by_id[self.other_novel.id])

        response = self.client.get(f"/api/wiki/novels/{self.novel.id}/characters")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["data"][0]["is_bookmarked"])

        response = self.client.get(f"/api/wiki/novels/{self.novel.id}/skills")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["data"][0]["is_bookmarked"])

        response = self.client.get(f"/api/wiki/novels/{self.novel.id}/items")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["data"][0]["is_bookmarked"])


if __name__ == "__main__":
    unittest.main()
