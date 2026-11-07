from test_accounts import PROFILE, TOKEN
from test_accounts import accounts as accounts


def test_dashboard_and_recommendation_pages_require_identity(accounts):
    client, api = accounts
    for route in ("/mon-espace", "/decouvrir"):
        assert client.get(route).status_code == 303
    client.set_cookie("cinevault_auth", TOKEN)
    api.statistics.return_value = {
        "catalogue": {
            "movies": 0,
            "copies": 0,
            "available": 0,
            "damaged": 0,
            "held_for_queue": 0,
            "by_support": {},
            "by_genre": {},
        },
        "personal": {
            "collection_entries": 0,
            "collection_movies": 0,
            "by_kind": {},
            "by_owned_support": {},
            "loans": {},
            "overdue": 0,
            "waiting_reservations": 0,
            "activity_retained": 0,
            "activity_last_7_days": 0,
            "recent_activity": [],
        },
    }
    page = client.get("/mon-espace")
    assert page.status_code == 200 and b"Votre espace" in page.data
    api.statistics.assert_called_once_with(TOKEN, "mine")
    assert page.headers["Cache-Control"] == "no-store"
    assert client.get("/mon-espace?scope=all").status_code == 403
    api.recommendations.return_value = {
        "recommendations": [],
        "personalized": False,
        "total": 0,
        "limit": 12,
        "method": "content-rules-v1",
    }
    page = client.get("/decouvrir?genre=Drame")
    assert page.status_code == 200 and "Aucun film à suggérer".encode() in page.data
    api.recommendations.assert_called_once_with(TOKEN, ["Drame"])
    assert client.get("/decouvrir?owner_id=other").status_code == 422


def test_recommendation_reasons_are_escaped_and_manager_scope_explicit(accounts):
    client, api = accounts
    client.set_cookie("cinevault_auth", TOKEN)
    api.me.return_value = {**PROFILE, "role": "manager"}
    api.statistics.return_value = {
        "catalogue": {
            "movies": 1,
            "copies": 1,
            "available": 1,
            "damaged": 0,
            "held_for_queue": 0,
            "by_support": {},
            "by_genre": {},
        },
        "personal": {
            "collection_entries": 0,
            "collection_movies": 0,
            "by_kind": {},
            "by_owned_support": {},
            "loans": {},
            "overdue": 0,
            "waiting_reservations": 0,
            "activity_retained": 0,
            "activity_last_7_days": 0,
            "recent_activity": [],
        },
        "operations": {
            "loans": {"pending": 1, "active": 2, "returned": 3, "cancelled": 0},
            "overdue": 1,
            "waiting_reservations": 0,
            "activity_last_7_days": {},
        },
    }
    assert client.get("/mon-espace?scope=all").status_code == 200
    api.statistics.assert_called_once_with(TOKEN, "all")
    api.recommendations.return_value = {
        "recommendations": [
            {
                "movie": {
                    "id": "movie-id",
                    "title": "<script>film</script>",
                    "year": 2024,
                    "director": "Camille",
                },
                "score": 5,
                "available_copies": 1,
                "reasons": [
                    {"code": "preferred_genre", "label": "<script>reason</script>", "points": 5}
                ],
            }
        ],
        "personalized": True,
        "total": 1,
        "limit": 12,
        "method": "content-rules-v1",
    }
    page = client.get("/decouvrir")
    assert page.status_code == 200 and b"&lt;script&gt;film&lt;/script&gt;" in page.data
    assert b"&lt;script&gt;reason&lt;/script&gt;" in page.data and b"<script>" not in page.data
