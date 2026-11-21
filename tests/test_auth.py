from tests.conftest import make_user


def test_t1_register_new_user(client):
    r = client.post("/auth/register", json={"username": "bob_1", "password": "password123"})
    assert r.status_code == 201
    assert r.json()["username"] == "bob_1"
    assert "password" not in r.text and "hashed" not in r.text


def test_t2_register_duplicate_username(client):
    body = {"username": "bob", "password": "password123"}
    client.post("/auth/register", json=body)
    assert client.post("/auth/register", json=body).status_code == 409


def test_t3_login_correct_credentials(client):
    client.post("/auth/register", json={"username": "bob", "password": "password123"})
    r = client.post("/auth/login", data={"username": "bob", "password": "password123"})
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer" and r.json()["access_token"]


def test_t4_login_wrong_password_and_unknown_user_same_message(client):
    client.post("/auth/register", json={"username": "bob", "password": "password123"})
    wrong = client.post("/auth/login", data={"username": "bob", "password": "nope-nope"})
    unknown = client.post("/auth/login", data={"username": "ghost", "password": "nope-nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_t5_no_token_is_401(client):
    assert client.get("/expenses").status_code == 401
    assert client.get("/expenses", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_me_returns_current_user(client):
    headers = make_user(client, "carol")
    assert client.get("/auth/me", headers=headers).json()["username"] == "carol"


def test_registration_validation(client):
    assert client.post("/auth/register", json={"username": "ab", "password": "password123"}).status_code == 422
    assert client.post("/auth/register", json={"username": "bad name!", "password": "password123"}).status_code == 422
    assert client.post("/auth/register", json={"username": "okname", "password": "short"}).status_code == 422
    assert client.post("/auth/register", json={"username": "okname", "password": "x" * 73}).status_code == 422
