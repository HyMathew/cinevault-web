import re

from flask import Blueprint,abort,g,render_template,request

from .accounts import api,signed_in,token
from .api_client import APIError,safe_poster

bp=Blueprint('metadata',__name__)
QID=re.compile(r'Q[1-9][0-9]{0,11}')


def target():
    identity=request.args.get('movie_id','')
    if len(request.args.getlist('movie_id'))>1: abort(422)
    movie=api().get(identity) if identity else None
    if identity and movie is None: abort(404)
    return movie


def role():
    if g.user['role'] not in ('manager','admin'): abort(403)


def unavailable(exc):
    if exc.status not in (422,429,503): raise exc
    return {422:'Vérifiez le titre ou l’identifiant recherché.',429:'Le fournisseur limite les demandes. Réessayez plus tard.',
        503:'La recherche externe est indisponible. Vous pouvez toujours ajouter un film manuellement.'}[exc.status]


@bp.get('/metadonnees')
@signed_in
def search():
    role()
    if set(request.args)-{'q','movie_id'} or len(request.args.getlist('q'))>1: abort(422)
    movie=target(); query=request.args.get('q',''); result=None; message=None; status=200
    if query:
        try: result=api().metadata_search(token(),query)
        except APIError as exc: message,status=unavailable(exc),exc.status
    return render_template('metadata_search.html',query=query,result=result,message=message,movie=movie),status


@bp.get('/metadonnees/<identity>')
@signed_in
def preview(identity):
    role()
    if not QID.fullmatch(identity) or set(request.args)-{'movie_id'}: abort(422)
    movie=target()
    try: result=api().metadata_detail(token(),identity)
    except APIError as exc:
        return render_template('metadata_search.html',query='',result=None,message=unavailable(exc),movie=movie),exc.status
    film=dict(result['film']); film['poster']=safe_poster(film.get('poster'))
    return render_template('metadata_preview.html',metadata=film,cache=result['cache'],movie=movie)
