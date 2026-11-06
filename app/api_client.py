"""Client HTTP du service de données ; aucune mutation n'est rejouée."""
from urllib.parse import quote

import requests


class APIError(Exception):
    def __init__(self, status, message, fields=None):
        super().__init__(message)
        self.status = status
        self.fields = fields or {}


class APIClient:
    def __init__(self, base_url, enterprise=False):
        self.base_url = base_url.rstrip('/')
        self.enterprise = enterprise

    def request(self, method, path, **kwargs):
        try:
            response = requests.request(method, self.base_url + path, timeout=(2, 5), allow_redirects=False, **kwargs)
        except requests.RequestException as exc:
            raise APIError(503, "Le service de données est indisponible.") from exc
        if 300 <= response.status_code < 400:
            raise APIError(503, 'Redirection inattendue du service de données.')
        if response.status_code >= 400:
            try:
                error = response.json().get('error', {})
            except (ValueError, AttributeError):
                error = {}
            if not isinstance(error, dict):
                error = {}
            raise APIError(response.status_code, error.get('message', 'Une erreur est survenue.'), error.get('fields'))
        if response.status_code == 204:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise APIError(503, "Réponse invalide du service de données.") from exc

    def list(self, q='', support=''):
        if self.enterprise:
            return self.search(q=q, support=support)['films']
        result = self.request('GET', '/api/films', params={'q': q, 'support': support})
        try:
            return result['films']
        except (KeyError, TypeError) as exc:
            raise APIError(503, 'Réponse invalide du service de données.') from exc

    def get(self, film_id):
        try:
            if self.enterprise:
                movie = self.request('GET', '/api/v1/movies/' + quote(film_id, safe=''))
                copies = self.copies(film_id)
                view=self.movie_view(movie,copies=copies)
                view['availability']=self.request('GET','/api/v1/availability',params={'movie_id':film_id})
                return view
            return self.request('GET', '/api/films/' + quote(film_id, safe=''))
        except APIError as exc:
            if exc.status == 404:
                return None
            raise

    def create(self, data, token=''):
        if self.enterprise:
            body = self.movie_payload(data)
            body['initial_copy'] = {'support':data['support'],'location':'','condition':'unknown'}
            movie = self.account_request(token,'POST','/movies',json=body)
            return self.movie_view(movie)
        return self.request('POST', '/api/films', json=data)

    def update(self, film_id, data, token='', version=''):
        if self.enterprise:
            movie = self.request('PUT','/api/v1/movies/'+quote(film_id,safe=''),
                                 headers={'Authorization':'Bearer '+token,'If-Match':version},json=self.movie_payload(data))
            return self.movie_view(movie)
        return self.request('PUT', '/api/films/' + quote(film_id, safe=''), json=data)

    def delete(self, film_id, token='', version=''):
        if self.enterprise:
            return self.request('DELETE','/api/v1/movies/'+quote(film_id,safe=''),
                                headers={'Authorization':'Bearer '+token,'If-Match':version})
        return self.request('DELETE', '/api/films/' + quote(film_id, safe=''))

    @staticmethod
    def movie_view(movie, copies=None, summary=None):
        summary = summary or {'count':len(copies or []),'supports':list(dict.fromkeys(c['support'] for c in copies or []))}
        return {'id':movie['id'],'titre':movie['title'],'annee':movie['year'],'realisateur':movie['director'],
                'acteurs':movie['actors'],'synopsis':movie['synopsis'],'genres':movie['genres'],'_etag':movie['_etag'],
                'support':summary['supports'][0] if summary['supports'] else 'autre',
                'copy_count':summary['count'],'copy_supports':summary['supports'],'copies':copies or []}

    @staticmethod
    def movie_payload(data):
        return {'title':data['titre'],'year':data['annee'],'director':data['realisateur'],
                'actors':data['acteurs'],'synopsis':data['synopsis'],'genres':data.get('genres',[])}

    def search(self, **query):
        result = self.request('GET','/api/v1/movies',params={k:v for k,v in query.items() if v != ''})
        return {'films':[self.movie_view(m,summary=result['copy_summaries'][m['id']]) for m in result['movies']],
                'total':result['total'],'limit':result['limit'],'offset':result['offset']}

    def copies(self, movie_id):
        return self.request('GET','/api/v1/copies',params={'movie_id':movie_id})['copies']

    def copy(self, copy_id):
        return self.request('GET','/api/v1/copies/'+quote(copy_id,safe=''))

    def create_copy(self, token, data):
        return self.account_request(token,'POST','/copies',json=data)

    def update_copy(self, token, copy_id, data, version):
        return self.request('PUT','/api/v1/copies/'+quote(copy_id,safe=''),
                            headers={'Authorization':'Bearer '+token,'If-Match':version},json=data)

    def delete_copy(self, token, copy_id, version):
        return self.request('DELETE','/api/v1/copies/'+quote(copy_id,safe=''),
                            headers={'Authorization':'Bearer '+token,'If-Match':version})

    def register(self, data):
        return self.request('POST', '/api/v1/auth/register', json=data)

    def login(self, data):
        return self.request('POST', '/api/v1/auth/login', json=data)

    def account_request(self, token, method, path, **kwargs):
        return self.request(method, '/api/v1' + path, headers={'Authorization':'Bearer ' + token}, **kwargs)

    def me(self, token):
        profile = self.account_request(token, 'GET', '/me')
        if not isinstance(profile, dict) or set(profile) != {'id','username','display_name','role','enabled'} or any(not isinstance(profile[k], str) for k in ('id','username','display_name','role')) or profile['role'] not in ('member','manager','admin') or profile['enabled'] is not True:
            raise APIError(503, 'Profil invalide du service de données.')
        return profile

    def logout(self, token):
        return self.account_request(token, 'POST', '/auth/logout')

    def update_profile(self, token, data):
        return self.account_request(token, 'PATCH', '/me', json=data)

    def change_password(self, token, data):
        return self.account_request(token, 'PUT', '/me/password', json=data)

    def users(self, token, offset=0):
        return self.account_request(token, 'GET', '/users', params={'limit':50,'offset':offset})

    def update_user(self, token, user_id, data):
        return self.account_request(token, 'PATCH', '/users/' + quote(user_id, safe=''), json=data)

    def collections(self, token, **query):
        return self.account_request(token,'GET','/collections',params={k:v for k,v in query.items() if v != ''})

    def collection_entry(self, token, entry_id):
        return self.account_request(token,'GET','/collections/'+quote(entry_id,safe=''))

    def create_entry(self, token, data):
        return self.account_request(token,'POST','/collections',json=data)

    def update_entry(self, token, entry_id, data, version):
        return self.request('PUT','/api/v1/collections/'+quote(entry_id,safe=''),
                            headers={'Authorization':'Bearer '+token,'If-Match':version},json=data)

    def delete_entry(self, token, entry_id, version):
        return self.request('DELETE','/api/v1/collections/'+quote(entry_id,safe=''),
                            headers={'Authorization':'Bearer '+token,'If-Match':version})

    def request_loan(self,token,data):
        return self.account_request(token,'POST','/loans',json=data)

    def loans(self,token,**query):
        return self.account_request(token,'GET','/loans',params={k:v for k,v in query.items() if v!=''})

    def loan(self,token,loan_id):
        return self.account_request(token,'GET','/loans/'+quote(loan_id,safe=''))

    def loan_options(self,token,loan_id):
        return self.account_request(token,'GET','/loans/'+quote(loan_id,safe='')+'/options')

    def loan_action(self,token,loan_id,action,version,data=None):
        if action not in ('approve','return','cancel'):
            raise ValueError('Unsupported loan action')
        return self.request('POST','/api/v1/loans/'+quote(loan_id,safe='')+'/'+action,
                            headers={'Authorization':'Bearer '+token,'If-Match':version},json=data)
