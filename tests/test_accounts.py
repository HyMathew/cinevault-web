"""Web boundary tests; API requests are simulated here, unlike Compose evidence."""
import re
from unittest.mock import Mock

import pytest

from app import create_app
from app.api_client import APIClient, APIError

PROFILE = {'id':'user-id', 'username':'alice','display_name':'<script>Alice</script>', 'role':'member','enabled':True}
TOKEN = 'synthetic-test-bearer-token-123456789'


@pytest.fixture
def accounts():
    api = Mock()
    api.me.return_value = PROFILE.copy()
    api.login.return_value = {'token':TOKEN,'token_type':'Bearer','expires_in':28800}
    api.update_profile.return_value = {**PROFILE, 'display_name':'Updated Alice'}
    api.reservations.return_value={'reservations':[],'positions':{},'ready_ids':[],'open_loan_ids':{},'total':0,'limit':24,'offset':0,'movies':{},'users':{}}
    api.loans.return_value={'loans':[],'total':0,'limit':24,'offset':0,'movies':{},'borrowers':{},'overdue_ids':[]}
    app = create_app({'TESTING':True,'SECRET_KEY':'only-for-unit-tests','ENTERPRISE_ENABLED':True,
                      'API_CLIENT':api, 'SESSION_COOKIE_SECURE':True})
    return app.test_client(), api


def csrf(response):
    return re.search(rb'name="csrf_token" value="([^"]+)"', response.data).group(1).decode()


def test_register_login_and_logout_require_csrf(accounts):
    client, api = accounts
    for route in ('/connexion','/inscription','/deconnexion','/profil','/profil/mot-de-passe'):
        assert client.post(route, data={}).status_code == 400
    token = csrf(client.get('/inscription'))
    response = client.post('/inscription', data={'csrf_token':token,'username':'alice',
                  'display_name':'Alice','password':'test passphrase 123','password_confirmation':'test passphrase 123'})
    assert response.status_code == 303 and response.headers['Location'].endswith('/connexion')
    api.register.assert_called_once_with({'username':'alice','display_name':'Alice','password':'test passphrase 123'})
    token = csrf(client.get('/connexion'))
    response = client.post('/connexion', data={'csrf_token':token,'username':'alice','password':'test passphrase 123'})
    assert response.status_code == 303 and response.headers['Location'].endswith('/profil')
    cookie = next(c for c in response.headers.getlist('Set-Cookie') if c.startswith('cinevault_auth='))
    assert 'HttpOnly' in cookie and 'SameSite=Lax' in cookie and 'Secure' in cookie and 'Max-Age=28800' in cookie
    profile = client.get('/profil')
    assert b'&lt;script&gt;Alice&lt;/script&gt;' in profile.data
    assert TOKEN.encode() not in profile.data
    assert 'test passphrase 123'.encode() not in profile.data
    assert client.post('/deconnexion', data={'csrf_token':token}).status_code == 400  # login rotates CSRF
    response = client.post('/deconnexion', data={'csrf_token':csrf(profile)})
    assert response.status_code == 303
    api.logout.assert_called_once_with(TOKEN)
    assert client.get_cookie('cinevault_auth') is None


def test_profile_password_and_privilege_checks(accounts):
    client, api = accounts
    assert client.get('/profil').status_code == 303
    client.set_cookie('cinevault_auth', TOKEN)
    token = csrf(client.get('/profil'))
    response = client.post('/profil', data={'csrf_token':token,'display_name':'Updated Alice'})
    assert response.status_code == 303
    api.update_profile.assert_called_once_with(TOKEN, {'display_name':'Updated Alice'})
    assert client.get('/administration').status_code == 403
    assert client.post('/administration/utilisateurs/another-id', data={'csrf_token':token,'role':'admin','enabled':'true'}).status_code == 403
    response = client.post('/profil/mot-de-passe', data={'csrf_token':token,'current_password':'old passphrase',
                           'new_password':'new passphrase 123','password_confirmation':'new passphrase 123'})
    assert response.status_code == 303
    api.change_password.assert_called_once_with(TOKEN, {'current_password':'old passphrase','new_password':'new passphrase 123'})
    assert client.get_cookie('cinevault_auth') is None


def test_errors_do_not_echo_password_and_api_down_does_not_retry(accounts):
    client, api = accounts
    token = csrf(client.get('/connexion'))
    api.login.side_effect = APIError(401, 'Password was not correct')
    response = client.post('/connexion', data={'csrf_token':token,'username':'alice','password':'private synthetic value'})
    assert response.status_code == 401
    assert b'private synthetic value' not in response.data
    assert b'value="alice"' in response.data
    api.login.side_effect = APIError(503, 'down')
    assert client.post('/connexion', data={'csrf_token':token,'username':'alice','password':'private synthetic value'}).status_code == 503
    assert api.login.call_count == 2
    client.set_cookie('cinevault_auth', TOKEN)
    api.me.side_effect = APIError(401, 'expired')
    assert client.get('/profil').status_code == 303
    assert client.get_cookie('cinevault_auth') is None


def test_api_bearer_relay_never_follows_redirects(monkeypatch):
    calls = []
    def redirect(method, url, **kwargs):
        calls.append((method,url,kwargs))
        response = Mock(status_code=302)
        return response
    monkeypatch.setattr('requests.request', redirect)
    with pytest.raises(APIError) as failure:
        APIClient('http://api:8000').me(TOKEN)
    assert failure.value.status == 503
    assert len(calls) == 1
    assert calls[0][1] == 'http://api:8000/api/v1/me'
    assert calls[0][2]['allow_redirects'] is False
    assert calls[0][2]['headers']['Authorization'] == 'Bearer ' + TOKEN


def test_admin_forms_relay_only_allowed_fields(accounts):
    client, api = accounts
    api.me.return_value = {**PROFILE,'role':'admin'}
    api.users.return_value = {'users':[PROFILE], 'total':1,'limit':50,'offset':0}
    client.set_cookie('cinevault_auth', TOKEN)
    page = client.get('/administration')
    assert page.status_code == 200
    token = csrf(page)
    response = client.post('/administration/utilisateurs/user-id', data={'csrf_token':token,'role':'manager','enabled':'true','password_hash':'injected'})
    assert response.status_code == 422
    response = client.post('/administration/utilisateurs/user-id', data={'csrf_token':token,'role':'manager','enabled':'true'})
    assert response.status_code == 303
    api.update_user.assert_called_once_with(TOKEN, 'user-id', {'role':'manager','enabled':True})


def test_non_ascii_csrf_is_rejected_and_security_headers_present(accounts):
    client, api = accounts
    client.get('/connexion')
    response = client.post('/connexion', data={'csrf_token':'é', 'username':'alice', 'password':'test passphrase 123'})
    assert response.status_code == 400
    api.login.assert_not_called()
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert "frame-ancestors 'none'" in response.headers['Content-Security-Policy']
    assert response.headers['Cache-Control'] == 'no-store'
