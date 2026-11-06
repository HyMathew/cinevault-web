from test_accounts import accounts, csrf, PROFILE, TOKEN
from app.api_client import APIClient, APIError

FILM = {'id':'film-id','titre':'Dune','annee':2021,'realisateur':'Denis Villeneuve','acteurs':['Acteur'],
        'synopsis':'Du sable.','genres':['Science-fiction'],'support':'blu-ray','copy_count':1,
        'copy_supports':['blu-ray'],'copies':[{'id':'copy-id','movie_id':'film-id','support':'blu-ray',
            'location':'A','condition':'good','_etag':'"copy-version"'}],'_etag':'"movie-version"'}


def setup_catalogue(api):
    api.search.return_value = {'films':[FILM],'total':25,'limit':24,'offset':0}
    api.get.return_value = FILM
    api.create.return_value = FILM
    api.update.return_value = FILM
    api.copy.return_value = FILM['copies'][0]


def test_public_catalogue_filters_pagination_and_no_management(accounts):
    client, api = accounts
    setup_catalogue(api)
    assert client.get('/').status_code == 200
    page = client.get('/films?genre=Science-fiction&sort=-year')
    assert page.status_code == 200
    assert b'Suivant' in page.data and b'offset=24' in page.data
    assert b'genre=Science-fiction' in page.data
    assert b'Ajouter un film' not in page.data
    assert client.get('/films/film-id').status_code == 200
    assert b'Modifier le film' not in client.get('/films/film-id').data
    assert client.get('/films/nouveau').status_code == 403
    client.set_cookie('cinevault_auth',TOKEN)
    assert client.get('/films/film-id/modifier').status_code == 403


def test_manager_forms_relay_version_and_preserve_stale_edits(accounts):
    client, api = accounts
    setup_catalogue(api)
    api.me.return_value = {**PROFILE,'role':'manager'}
    client.set_cookie('cinevault_auth',TOKEN)
    page = client.get('/films/film-id/modifier')
    assert page.status_code == 200 and b'name="version"' in page.data
    assert b'name="support"' not in page.data  # copies are edited separately
    token = csrf(page)
    body = {'csrf_token':token,'version':'"movie-version"','titre':'Dune modifié','annee':'2021',
            'realisateur':'Denis Villeneuve','acteurs':'Acteur','synopsis':'Texte saisi','genres':'Science-fiction, Drame'}
    assert client.post('/films/film-id/modifier',data=body).status_code == 303
    assert api.update.call_args.kwargs == {'token':TOKEN,'version':'"movie-version"'}
    assert api.update.call_args.args[1]['genres'] == ['Science-fiction','Drame']
    api.update.side_effect = APIError(412,'stale')
    page = client.post('/films/film-id/modifier',data=body)
    assert page.status_code == 412 and b'Texte saisi' in page.data
    assert 'Dune modifié'.encode() in page.data
    assert client.get('/films/film-id/supprimer').status_code == 200
    assert b'>Confirmer la suppression</button>' not in client.get('/films/film-id/supprimer').data


def test_copy_management_forms_and_movie_binding(accounts):
    client, api = accounts
    setup_catalogue(api)
    api.me.return_value = {**PROFILE,'role':'manager'}
    client.set_cookie('cinevault_auth',TOKEN)
    token = csrf(client.get('/films/film-id/exemplaires/nouveau'))
    body = {'csrf_token':token,'support':'dvd','location':'Rayon B','condition':'good','operation_key':'synthetic-copy-operation-123456'}
    assert client.post('/films/film-id/exemplaires/nouveau',data=body).status_code == 303
    api.create_copy.assert_called_once_with(TOKEN,{'movie_id':'film-id','support':'dvd','location':'Rayon B','condition':'good'},operation_key=body['operation_key'])
    page = client.get('/films/film-id/exemplaires/copy-id/modifier')
    assert page.status_code == 200
    assert client.post('/films/film-id/exemplaires/copy-id/modifier',data={**body,'version':'"copy-version"'}).status_code == 303
    api.update_copy.assert_called_once_with(TOKEN,'copy-id',{'support':'dvd','location':'Rayon B','condition':'good'},'"copy-version"')
    assert client.post('/films/film-id/exemplaires/copy-id/supprimer',data={'csrf_token':token,'version':'"copy-version"'}).status_code == 303
    api.delete_copy.assert_called_once_with(TOKEN,'copy-id','"copy-version"')
    api.copy.return_value = {**FILM['copies'][0],'movie_id':'another-film'}
    assert client.get('/films/film-id/exemplaires/copy-id/modifier').status_code == 404


def test_enterprise_client_sends_version_and_canonical_metadata(monkeypatch):
    calls = []
    class Response:
        status_code = 200
        def json(self):
            return {'id':'film-id','title':'Dune','year':2021,'director':'Denis Villeneuve',
                    'actors':[],'synopsis':'Synopsis','genres':[],'_etag':'"next"'}
    def request(method,url,**kwargs):
        calls.append((method,url,kwargs))
        return Response()
    monkeypatch.setattr('requests.request',request)
    client = APIClient('http://api',enterprise=True)
    data = {'titre':'Dune','annee':2021,'realisateur':'Denis Villeneuve','acteurs':[],
            'synopsis':'Synopsis','genres':[],'support':'dvd'}
    assert client.update('film-id',data,TOKEN,'"old"')['titre'] == 'Dune'
    assert calls[0][0:2] == ('PUT','http://api/api/v1/movies/film-id')
    assert calls[0][2]['headers'] == {'Authorization':'Bearer '+TOKEN,'If-Match':'"old"'}
    assert 'support' not in calls[0][2]['json']


def test_copy_timeout_preserves_operation_key_without_automatic_retry(accounts):
    client,api=accounts
    setup_catalogue(api)
    api.me.return_value={**PROFILE,'role':'manager'}
    client.set_cookie('cinevault_auth',TOKEN)
    page=client.get('/films/film-id/exemplaires/nouveau')
    import re
    key=re.search(rb'name="operation_key" value="([^"]+)"',page.data).group(1).decode()
    api.create_copy.side_effect=APIError(503,'uncertain')
    response=client.post('/films/film-id/exemplaires/nouveau',data={'csrf_token':csrf(page),
        'operation_key':key,'support':'dvd','location':'Saved value','condition':'good'})
    assert response.status_code==503 and key.encode() in response.data and b'Saved value' in response.data
    assert api.create_copy.call_count==1
