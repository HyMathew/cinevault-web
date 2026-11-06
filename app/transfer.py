"""File transfers terminate here; the API receives a JSON carrier only."""
import json
import secrets

from flask import Blueprint, Response, abort, g, render_template, request

from .accounts import api, signed_in, token
from .api_client import APIError

bp=Blueprint('transfer',__name__)
MAX_FILE=1024*1024


def require_manager():
    if g.user['role'] not in ('manager','admin'):
        abort(403)


@bp.route('/transfert',methods=['GET','POST'])
@signed_in
def catalogue():
    require_manager()
    key=request.form.get('operation_key','') if request.method=='POST' else secrets.token_urlsafe(32)
    format=request.form.get('format','json')
    policy=request.form.get('duplicate_policy','reject')
    message,result,status=None,None,200
    if request.method=='POST':
        if not key:
            abort(400,description='Rouvrez le formulaire avant un import.')
        file=request.files.get('file')
        if format not in ('json','csv') or policy not in ('reject','skip','append_copies') or file is None:
            message,status='Choisissez un fichier, un format et une politique valides.',422
        else:
            raw=file.stream.read(MAX_FILE+1)
            try:
                if len(raw)>MAX_FILE:
                    raise ValueError()
                content=raw.decode('utf-8-sig')
            except (UnicodeError,ValueError):
                message,status='Fichier UTF-8 requis, de 1 Mio maximum.',422
            else:
                try:
                    result=api().import_catalogue(token(),{'format':format,'content':content,'duplicate_policy':policy},key)
                    key=secrets.token_urlsafe(32)
                except APIError as exc:
                    if exc.status not in (409,422,428,503):
                        raise
                    status=exc.status
                    message={409:'Conflit : aucun nouveau lot appliqué. Vérifiez le catalogue et la politique choisie. Une clé déjà utilisée exige le même fichier et les mêmes options.',
                        422:'Le fichier est invalide. Vérifiez le format, les colonnes et les limites.',
                        428:'La clé d’opération manque. Rouvrez cette page.',
                        503:'Le résultat n’a pas pu être confirmé. Vérifiez le catalogue ; pour répéter cet envoi, sélectionnez le même fichier et gardez les mêmes options. La clé a été conservée.'}[status]
    return render_template('enterprise_transfer.html',operation_key=key,format=format,policy=policy,message=message,result=result),status


@bp.get('/transfert/export')
@signed_in
def download():
    require_manager()
    format=request.args.get('format','json')
    if set(request.args)-{'format'} or len(request.args.getlist('format'))>1 or format not in ('json','csv'):
        abort(422)
    data=api().export_catalogue(token(),format)
    if not isinstance(data,dict) or data.get('format')!=format or (format=='csv' and not isinstance(data.get('content'),str)) or (format=='json' and not isinstance(data.get('content'),dict)):
        raise APIError(503,'Export invalide du service de données.')
    content=data['content'] if format=='csv' else json.dumps(data['content'],ensure_ascii=False,indent=2)+'\n'
    response=Response(content,content_type='text/csv; charset=utf-8' if format=='csv' else 'application/json; charset=utf-8')
    response.headers['Content-Disposition']='attachment; filename="cinevault-catalogue.'+format+'"'
    response.headers['Cache-Control']='no-store'
    return response
