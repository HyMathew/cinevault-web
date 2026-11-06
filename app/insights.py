from datetime import datetime,timezone

from flask import Blueprint,abort,g,render_template,request

from .accounts import api,signed_in,token

bp=Blueprint('insights',__name__)
LOAN_LABELS={'pending':'Demandes en attente','active':'En prêt','returned':'Retournés','cancelled':'Annulés'}
ACTIVITY_LABELS={**{kind+'.'+action:label for kind in ('movie','copy','collection') for action,label in
    (('created','Ajout enregistré'),('updated','Modification enregistrée'),('deleted','Retrait enregistré'))},
    'loan.requested':'Demande de prêt','loan.approved':'Prêt validé','loan.returned':'Retour enregistré','loan.cancelled':'Demande annulée',
    'reservation.created':'Réservation créée','reservation.fulfilled':'Réservation attribuée','reservation.cancelled':'Réservation annulée','reservation.expired':'Réservation expirée',
    'import.completed':'Catalogue importé','import.failed':'Import refusé','export.completed':'Catalogue exporté'}


@bp.app_template_filter('date_utc')
def date_utc(value):
    return datetime.fromtimestamp(value,timezone.utc).strftime('%d/%m/%Y à %H:%M UTC')


@bp.get('/mon-espace')
@signed_in
def dashboard():
    scope=request.args.get('scope','mine')
    if set(request.args)-{'scope'} or len(request.args.getlist('scope'))>1 or scope not in ('mine','all'):
        abort(422)
    if scope=='all' and g.user['role'] not in ('manager','admin'):
        abort(403)
    return render_template('enterprise_dashboard.html',result=api().statistics(token(),scope),scope=scope,
        loan_labels=LOAN_LABELS,activity_labels=ACTIVITY_LABELS)


@bp.get('/decouvrir')
@signed_in
def discover():
    genres=request.args.getlist('genre')
    if set(request.args)-{'genre'} or len(genres)>10 or any(len(genre)>80 for genre in genres):
        abort(422)
    genres=[genre for genre in genres if genre]
    return render_template('enterprise_discover.html',result=api().recommendations(token(),genres),genres=genres)
