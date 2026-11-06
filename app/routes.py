from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for

from .api_client import APIError
from .forms import validate

pages = Blueprint('pages', __name__)


def api():
    return current_app.extensions['cinevault_api']


@pages.get('/')
def home():
    films = api().list()
    return render_template('home.html', films=films)


@pages.get('/films')
def catalogue():
    q = request.args.get('q', '').strip()
    support = request.args.get('support', '')
    return render_template('catalogue.html', films=api().list(q, support), q=q, support=support)


@pages.get('/films/<film_id>')
def detail(film_id):
    film = api().get(film_id)
    if film is None:
        abort(404)
    return render_template('detail.html', film=film)


@pages.route('/films/nouveau', methods=['GET', 'POST'])
@pages.route('/films/<film_id>/modifier', methods=['GET', 'POST'])
def film_form(film_id=None):
    editing = film_id is not None
    film = api().get(film_id) if editing and request.method == 'GET' else {}
    if editing and request.method == 'GET' and film is None:
        abort(404)
    values = dict(film)
    if editing:
        values['acteurs'] = ', '.join(values.get('acteurs', []))
    errors = {}
    message = None
    if request.method == 'POST':
        values = request.form.to_dict()
        data, errors = validate(request.form)
        if not errors:
            try:
                result = api().update(film_id, data) if editing else api().create(data)
            except APIError as exc:
                if exc.status == 404:
                    abort(404)
                if exc.status == 422:
                    errors = exc.fields
                    message = str(exc)
                else:
                    message = 'Le service de données est indisponible. Vos champs sont conservés ; vérifiez le résultat avant de réessayer.'
                    return render_template('form.html', editing=editing, values=values, errors=errors, message=message), 503
            else:
                flash('Film enregistré.')
                return redirect(url_for('pages.detail', film_id=result['id']), code=303)
        return render_template('form.html', editing=editing, values=values, errors=errors, message=message), 422
    return render_template('form.html', editing=editing, values=values, errors=errors, message=message)


@pages.route('/films/<film_id>/supprimer', methods=['GET', 'POST'])
def delete(film_id):
    film = api().get(film_id)
    if film is None:
        abort(404)
    if request.method == 'POST':
        api().delete(film_id)
        flash('Film supprimé.')
        return redirect(url_for('pages.catalogue'), code=303)
    return render_template('delete.html', film=film)


@pages.get('/page-simple')
def simple():
    return render_template('simple.html')


@pages.get('/health')
def health():
    return {'status': 'ok'}
