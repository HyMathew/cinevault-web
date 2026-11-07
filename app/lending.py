import re
from datetime import datetime, time, timedelta, timezone

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from .accounts import signed_in, token
from .api_client import APIError

bp = Blueprint("lending", __name__)
STATUSES = {
    "pending": "En attente",
    "active": "En prêt",
    "returned": "Retourné",
    "cancelled": "Annulé",
}
RESERVATION_STATUSES = {
    "waiting": "En attente",
    "fulfilled": "Attribuée",
    "cancelled": "Annulée",
    "expired": "Expirée",
}


def api():
    return current_app.extensions["cinevault_api"]


def require_manager():
    if g.user["role"] not in ("manager", "admin"):
        abort(403)


@bp.app_context_processor
def labels():
    return {"loan_statuses": STATUSES, "reservation_statuses": RESERVATION_STATUSES}


@bp.app_template_filter("utc_date")
def utc_date(timestamp):
    if timestamp is None:
        return "—"
    try:
        return datetime.fromtimestamp(timestamp, timezone.utc).strftime("%d/%m/%Y")
    except (ValueError, OverflowError, OSError):
        return "Date invalide"


@bp.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.get("/emprunts")
@signed_in
def loan_list():
    query = request.args.to_dict()
    return render_template("loan_list.html", result=api().loans(token(), **query), query=query)


@bp.post("/films/<film_id>/emprunter")
@signed_in
def request_loan(film_id):
    api().request_loan(token(), {"movie_id": film_id})
    flash("Votre demande de prêt a été envoyée à la vidéothèque.")
    return redirect(url_for("lending.loan_list"), code=303)


@bp.route("/emprunts/<loan_id>/valider", methods=["GET", "POST"])
@signed_in
def approve(loan_id):
    require_manager()
    loan = api().loan(token(), loan_id)
    options = api().loan_options(token(), loan_id)
    today = datetime.now(timezone.utc).date()
    values = {
        "copy_id": "",
        "due_date": (today + timedelta(days=14)).isoformat(),
        "version": loan["_etag"],
    }
    message = None
    if request.method == "POST":
        values = {k: request.form.get(k, "") for k in ("copy_id", "due_date", "version")}
        try:
            if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", values["due_date"]):
                raise ValueError()
            date = datetime.strptime(values["due_date"], "%Y-%m-%d").date()
            due_at = int(datetime.combine(date, time(23, 59, 59), timezone.utc).timestamp())
        except ValueError:
            message = "Indiquez une date de retour valide."
            status = 422
        else:
            try:
                api().loan_action(
                    token(),
                    loan_id,
                    "approve",
                    values["version"],
                    {"copy_id": values["copy_id"], "due_at": due_at},
                )
            except APIError as exc:
                if exc.status not in (409, 412, 422, 428):
                    raise
                message = (
                    "Cet exemplaire ou cette demande n’est plus disponible. Vérifiez les informations avant de réessayer."
                    if exc.status in (409, 412, 428)
                    else "Vérifiez l’exemplaire et la date de retour (90 jours maximum)."
                )
                status = exc.status
            else:
                flash("Le prêt a été validé.")
                return redirect(url_for("lending.loan_list"), code=303)
        return render_template(
            "loan_approve.html",
            loan=loan,
            options=options,
            values=values,
            message=message,
            min_date=today.isoformat(),
            max_date=(today + timedelta(days=89)).isoformat(),
        ), status
    return render_template(
        "loan_approve.html",
        loan=loan,
        options=options,
        values=values,
        message=message,
        min_date=today.isoformat(),
        max_date=(today + timedelta(days=89)).isoformat(),
    )


@bp.post("/emprunts/<loan_id>/retour")
@signed_in
def record_return(loan_id):
    require_manager()
    api().loan_action(token(), loan_id, "return", request.form.get("version", ""))
    flash("Le retour a été enregistré.")
    return redirect(url_for("lending.loan_list"), code=303)


@bp.post("/emprunts/<loan_id>/annuler")
@signed_in
def cancel(loan_id):
    api().loan_action(token(), loan_id, "cancel", request.form.get("version", ""))
    flash("La demande a été annulée.")
    return redirect(url_for("lending.loan_list"), code=303)


@bp.get("/reservations")
@signed_in
def reservation_list():
    query = request.args.to_dict()
    return render_template(
        "reservation_list.html", result=api().reservations(token(), **query), query=query
    )


@bp.post("/films/<film_id>/reserver")
@signed_in
def request_reservation(film_id):
    try:
        api().request_reservation(token(), {"movie_id": film_id})
    except APIError as exc:
        if exc.status != 409:
            raise
        return render_template("reservation_conflict.html", film_id=film_id), 409
    flash("Votre réservation a été enregistrée dans la file d’attente.")
    return redirect(url_for("lending.reservation_list"), code=303)


@bp.post("/reservations/<reservation_id>/annuler")
@signed_in
def cancel_reservation(reservation_id):
    api().cancel_reservation(token(), reservation_id, request.form.get("version", ""))
    flash("La réservation a été annulée.")
    return redirect(url_for("lending.reservation_list"), code=303)
