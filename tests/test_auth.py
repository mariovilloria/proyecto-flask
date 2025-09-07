def test_login_page(client):
    rv = client.get("/auth/login")
    assert rv.status_code == 200
    assert "Iniciar Sesión".encode("utf-8") in rv.data

def test_login_fail(client):
    rv = client.post("/auth/login", data={"cedula": "999", "password": "wrong"})
    assert "Credenciales inválidas".encode("utf-8") in rv.data