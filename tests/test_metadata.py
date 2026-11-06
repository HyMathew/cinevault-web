from test_accounts import accounts,csrf,PROFILE,TOKEN
from test_enterprise_catalogue import FILM,setup_catalogue
from app.api_client import APIError,APIClient

META={'film':{'id':'Q151599','title':'Metropolis','year':1927,'director':'Fritz Lang','actors':['Brigitte Helm'],
    'genres':['Science-fiction'],'description':'Description courte','source_url':'https://www.wikidata.org/wiki/Q151599',
    'revision':123,'retrieved_at':1700000000,'poster':None,'warnings':[]},
    'cache':{'status':'fresh','stored_at':1700000000,'hit':False}}


def test_external_search_preview_and_manual_creation_are_manager_only(accounts):
    client,api=accounts
    assert client.get('/metadonnees').status_code==303
    client.set_cookie('cinevault_auth',TOKEN)
    assert client.get('/metadonnees').status_code==403
    api.me.return_value={**PROFILE,'role':'manager'}
    api.metadata_search.return_value={'items':[{'id':'Q151599','title':'Metropolis','description':'Film de 1927','source_url':'https://www.wikidata.org/wiki/Q151599'}],
        'cache':{'status':'fresh','stored_at':1700000000,'hit':False}}
    api.metadata_detail.return_value=META
    page=client.get('/metadonnees?q=Metropolis')
    assert page.status_code==200 and b'Metropolis' in page.data
    preview=client.get('/metadonnees/Q151599')
    assert preview.status_code==200 and b'Description courte' in preview.data
    setup_catalogue(api)
    form=client.get('/films/nouveau?metadata_id=Q151599')
    assert form.status_code==200 and b'value="Metropolis"' in form.data and b'name="external_id" value="Q151599"' in form.data
    response=client.post('/films/nouveau',data={'csrf_token':csrf(form),'external_id':'Q151599','titre':'Metropolis','annee':'1927',
        'realisateur':'Fritz Lang','acteurs':'Brigitte Helm','genres':'Science-fiction','synopsis':'Résumé vérifié','support':'dvd'})
    assert response.status_code==303 and api.create.call_args.args[0]['external_id']=='Q151599'


def test_enrichment_does_not_silently_replace_existing_synopsis_and_outage_is_recoverable(accounts):
    client,api=accounts
    setup_catalogue(api); api.metadata_detail.return_value=META
    api.me.return_value={**PROFILE,'role':'manager'}; client.set_cookie('cinevault_auth',TOKEN)
    page=client.get('/films/film-id/modifier?metadata_id=Q151599')
    assert page.status_code==200 and b'Du sable.' in page.data and b'value="Metropolis"' in page.data
    assert b'name="version"' in page.data
    api.metadata_search.side_effect=APIError(503,'provider down')
    page=client.get('/metadonnees?q=Metropolis')
    assert page.status_code==503 and b'Ajouter manuellement' in page.data
    assert client.get('/films').status_code==200
    assert client.get('/films?include_posters=true').status_code==422


def test_metadata_http_timeout_is_local_to_external_requests(monkeypatch):
    calls=[]
    class Response:
        status_code=200
        def json(self): return META
    def request(method,url,**kwargs): calls.append(kwargs); return Response()
    monkeypatch.setattr('requests.request',request)
    api=APIClient('http://api',enterprise=True)
    api.metadata_detail(TOKEN,'Q151599')
    assert calls[-1]['timeout']==(2,25) and calls[-1]['allow_redirects'] is False
    api.request('GET','/health')
    assert calls[-1]['timeout']==(2,5)
