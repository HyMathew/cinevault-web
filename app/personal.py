"""Private collection screens; ownership is always checked by the API."""
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for

from .accounts import signed_in, token
from .api_client import APIError

bp = Blueprint('personal',__name__)
KINDS = {'owned':'Films possédés','favorite':'Favoris','watched':'Films vus',
         'watchlist':'Films à voir','custom':'Listes personnelles'}


def api():
    return current_app.extensions['cinevault_api']


@bp.app_context_processor
def labels():
    return {'collection_kinds':KINDS}


@bp.after_request
def no_cache(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.get('/ma-collection')
@signed_in
def collection_list():
    query = request.args.to_dict()
    return render_template('personal_collection.html',result=api().collections(token(),**query),query=query)


@bp.route('/ma-collection/ajouter',methods=['GET','POST'])
@bp.route('/ma-collection/<entry_id>/modifier',methods=['GET','POST'])
@signed_in
def entry_form(entry_id=None):
    entry = api().collection_entry(token(),entry_id) if entry_id else None
    movie_id = entry['movie_id'] if entry else request.values.get('film_id','')
    film = api().get(movie_id)
    if film is None:
        abort(404)
    values = dict(entry) if entry else {'kind':'favorite','list_name':'','supports':[]}
    message = None
    if request.method == 'POST':
        values = {'kind':entry['kind'] if entry else request.form.get('kind',''),
                  'list_name':request.form.get('list_name',''),'supports':request.form.getlist('supports'),
                  'version':request.form.get('version','')}
        body = {k:values[k] for k in ('list_name','supports')}
        try:
            if entry:
                api().update_entry(token(),entry_id,body,values['version'])
            else:
                api().create_entry(token(),{'movie_id':movie_id,'kind':values['kind'],**body})
        except APIError as exc:
            if exc.status not in (409,412,422,428):
                raise
            message = {409:'Ce film figure déjà dans cette partie de votre collection.',
                       412:'Cette entrée a changé. Rechargez-la et comparez vos modifications.',
                       422:'Vérifiez le type, le nom de liste et les supports autorisés.',
                       428:'Rechargez cette entrée avant de la modifier.'}[exc.status]
            return render_template('personal_entry_form.html',film=film,values=values,editing=bool(entry),message=message),exc.status
        flash('Votre collection a été mise à jour.')
        return redirect(url_for('personal.collection_list'),code=303)
    return render_template('personal_entry_form.html',film=film,values=values,editing=bool(entry),message=message)


@bp.post('/ma-collection/<entry_id>/retirer')
@signed_in
def delete_entry(entry_id):
    api().delete_entry(token(),entry_id,request.form.get('version',''))
    flash('Film retiré de cette partie de votre collection.')
    return redirect(url_for('personal.collection_list'),code=303)
