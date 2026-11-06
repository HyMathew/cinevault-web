import secrets
from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for

from .api_client import APIError
from .forms import validate

pages = Blueprint('pages', __name__)


def api():
    return current_app.extensions['cinevault_api']


def enterprise():
    return current_app.config['ENTERPRISE_ENABLED'] is True


def require_manager():
    if enterprise() and (not g.user or g.user['role'] not in ('manager','admin')):
        abort(403)


def auth_token():
    return request.cookies.get('cinevault_auth','')


@pages.get('/')
def home():
    if enterprise():
        result = api().search(limit=5)
        return render_template('enterprise_home.html', **result)
    films = api().list()
    return render_template('home.html', films=films)


@pages.get('/films')
def catalogue():
    if enterprise():
        if set(request.args)-{'q','genre','year','support','sort','limit','offset'} or any(len(request.args.getlist(key))!=1 for key in request.args):
            abort(422)
        query = request.args.to_dict()
        result = api().search(include_posters=True,**query)
        return render_template('enterprise_catalogue.html', **result, query=query)
    q = request.args.get('q', '').strip()
    support = request.args.get('support', '')
    return render_template('catalogue.html', films=api().list(q, support), q=q, support=support)


@pages.get('/films/<film_id>')
def detail(film_id):
    film = api().get(film_id)
    if film is None:
        abort(404)
    own_reservations={'reservations':[],'positions':{},'ready_ids':[],'open_loan_ids':{}}
    if enterprise() and g.user:
        own_reservations=api().reservations(auth_token(),status='waiting',scope='mine',movie_id=film_id)
    return render_template('enterprise_detail.html' if enterprise() else 'detail.html',film=film,own_reservations=own_reservations)


@pages.route('/films/nouveau', methods=['GET', 'POST'])
@pages.route('/films/<film_id>/modifier', methods=['GET', 'POST'])
def film_form(film_id=None):
    require_manager()
    template = 'enterprise_movie_form.html' if enterprise() else 'form.html'
    editing = film_id is not None
    film = api().get(film_id) if editing and request.method == 'GET' else {}
    if editing and request.method == 'GET' and film is None:
        abort(404)
    values = dict(film)
    if editing:
        values['acteurs'] = ', '.join(values.get('acteurs', []))
    errors = {}
    message = None
    if enterprise() and request.method=='GET' and request.args.get('metadata_id'):
        try:
            metadata=api().metadata_detail(auth_token(),request.args['metadata_id'])['film']
        except APIError as exc:
            if exc.status not in (422,429,503): raise
            message='La proposition externe est indisponible. Vos données restent présentes ; vous pouvez continuer manuellement.'
        else:
            values.update({key:value for key,value in {'titre':metadata['title'],'annee':metadata['year'],
                'realisateur':metadata['director'],'acteurs':', '.join(metadata['actors']),'genres':metadata['genres']}.items() if value})
            if not values.get('synopsis'): values['synopsis']=metadata['description']
            values['external_id']=metadata['id']
            message='Proposition Wikidata préremplie. Vérifiez les champs et complétez le résumé avant enregistrement.'
    if request.method == 'POST':
        values = request.form.to_dict()
        form_data = request.form.to_dict()
        if enterprise() and editing:
            form_data['support'] = 'autre'
        data, errors = validate(form_data)
        if enterprise():
            data['genres'] = [x.strip() for x in request.form.get('genres','').split(',') if x.strip()]
            if request.form.get('clear_external')=='1': data['external_id']=None
            elif request.form.get('external_id'): data['external_id']=request.form['external_id']
        if not errors:
            try:
                if enterprise():
                    result = api().update(film_id,data,token=auth_token(),version=request.form.get('version','')) if editing else api().create(data,token=auth_token())
                else:
                    result = api().update(film_id, data) if editing else api().create(data)
            except APIError as exc:
                if enterprise() and exc.status in (401,403):
                    raise
                if exc.status == 404:
                    abort(404)
                if enterprise() and exc.status in (409,412,428,429):
                    if exc.status==429:
                        return render_template(template,editing=editing,values=values,errors={},message='Le fournisseur limite les demandes. Vos champs sont conservés ; réessayez plus tard.'),429
                    message = 'Ce film existe déjà.' if exc.status == 409 else 'Ce film a changé. Vos champs sont conservés ; rechargez sa fiche et comparez les modifications avant de réessayer.'
                    return render_template(template,editing=editing,values=values,errors={},message=message),exc.status
                if exc.status == 422:
                    errors = exc.fields
                    message = str(exc)
                else:
                    message = 'Le service de données est indisponible. Vos champs sont conservés ; vérifiez le résultat avant de réessayer.'
                    return render_template(template, editing=editing, values=values, errors=errors, message=message), 503
            else:
                flash('Film enregistré.')
                return redirect(url_for('pages.detail', film_id=result['id']), code=303)
        return render_template(template, editing=editing, values=values, errors=errors, message=message), 422
    return render_template(template, editing=editing, values=values, errors=errors, message=message)


@pages.route('/films/<film_id>/supprimer', methods=['GET', 'POST'])
def delete(film_id):
    require_manager()
    film = api().get(film_id)
    if film is None:
        abort(404)
    if request.method == 'POST':
        if enterprise():
            api().delete(film_id,token=auth_token(),version=request.form.get('version',''))
        else:
            api().delete(film_id)
        flash('Film supprimé.')
        return redirect(url_for('pages.catalogue'), code=303)
    return render_template('delete.html', film=film)


@pages.route('/films/<film_id>/exemplaires/nouveau',methods=['GET','POST'])
@pages.route('/films/<film_id>/exemplaires/<copy_id>/modifier',methods=['GET','POST'])
def copy_form(film_id,copy_id=None):
    if not enterprise():
        abort(404)
    require_manager()
    film = api().get(film_id)
    if film is None:
        abort(404)
    values = api().copy(copy_id) if copy_id else {'support':'','location':'','condition':'unknown'}
    if not copy_id:
        values['operation_key']=secrets.token_urlsafe(32)
    if copy_id and values['movie_id'] != film_id:
        abort(404)
    message = None
    if request.method == 'POST':
        values = request.form.to_dict()
        if not copy_id and not values.get('operation_key'):
            abort(400,description='Rouvrez le formulaire avant de créer un exemplaire.')
        data = {k:request.form.get(k,'') for k in ('support','location','condition')}
        try:
            if copy_id:
                api().update_copy(auth_token(),copy_id,data,request.form.get('version',''))
            else:
                api().create_copy(auth_token(),{'movie_id':film_id,**data},operation_key=values['operation_key'])
        except APIError as exc:
            if exc.status not in (422,409,412,428,503):
                raise
            message = {422:'Vérifiez les champs.',409:'Ce formulaire a déjà servi avec d’autres valeurs. Vérifiez la fiche puis ouvrez un nouveau formulaire.',
                412:'Cet exemplaire a changé. Rechargez-le avant de réessayer.',428:'Rechargez cet exemplaire avant de réessayer.',
                503:'Le résultat n’a pas pu être confirmé. Vos champs sont conservés ; vérifiez la fiche avant de réessayer.'}[exc.status]
            return render_template('enterprise_copy_form.html',film=film,values=values,editing=bool(copy_id),message=message),exc.status
        return redirect(url_for('pages.detail',film_id=film_id),code=303)
    return render_template('enterprise_copy_form.html',film=film,values=values,editing=bool(copy_id),message=message)


@pages.post('/films/<film_id>/exemplaires/<copy_id>/supprimer')
def delete_copy(film_id,copy_id):
    if not enterprise():
        abort(404)
    require_manager()
    copy = api().copy(copy_id)
    if copy['movie_id'] != film_id:
        abort(404)
    api().delete_copy(auth_token(),copy_id,request.form.get('version',''))
    return redirect(url_for('pages.detail',film_id=film_id),code=303)


@pages.get('/page-simple')
def simple():
    return render_template('simple.html')


@pages.get('/health')
def health():
    return {'status': 'ok'}
