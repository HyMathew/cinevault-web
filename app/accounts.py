"""Account presentation; the API remains the authority for every permission."""

import re
from functools import wraps

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from .api_client import APIError

bp = Blueprint("accounts", __name__)
COOKIE = "cinevault_auth"
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{20,128}")


def api():
    return current_app.extensions["cinevault_api"]


def token():
    return request.cookies.get(COOKIE, "")


def clear_auth(response):
    response.delete_cookie(
        COOKIE,
        path="/",
        secure=current_app.config["SESSION_COOKIE_SECURE"],
        httponly=True,
        samesite="Lax",
    )
    session.clear()
    return response


def signed_in(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            return redirect(url_for("accounts.login"), code=303)
        return view(*args, **kwargs)

    return wrapped


def account_error(exc, template, **context):
    messages = {
        401: "Identifiant ou mot de passe invalide.",
        403: "Cette action est interdite.",
        409: "Cette opération entre en conflit avec les données actuelles.",
        422: "Vérifiez les champs et les règles indiquées.",
        429: "Trop de tentatives. Réessayez dans quelques minutes.",
    }
    if exc.status not in messages:
        raise exc
    headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after is not None else {}
    return render_template(template, message=messages[exc.status], **context), exc.status, headers


@bp.route("/inscription", methods=["GET", "POST"])
def register():
    username, display_name = "", ""
    if request.method == "POST":
        username, display_name = (
            request.form.get("username", ""),
            request.form.get("display_name", ""),
        )
        if request.form.get("password") != request.form.get("password_confirmation"):
            return render_template(
                "account_auth.html",
                registering=True,
                username=username,
                display_name=display_name,
                message="Les mots de passe ne correspondent pas.",
            ), 422
        try:
            api().register(
                {
                    "username": username,
                    "display_name": display_name,
                    "password": request.form.get("password", ""),
                }
            )
        except APIError as exc:
            return account_error(
                exc,
                "account_auth.html",
                registering=True,
                username=username,
                display_name=display_name,
            )
        flash("Compte créé. Vous pouvez vous connecter.")
        return redirect(url_for("accounts.login"), code=303)
    return render_template(
        "account_auth.html", registering=True, username=username, display_name=display_name
    )


@bp.route("/connexion", methods=["GET", "POST"])
def login():
    username = request.form.get("username", "")
    if request.method == "POST":
        try:
            result = api().login(
                {"username": username, "password": request.form.get("password", "")}
            )
        except APIError as exc:
            return account_error(exc, "account_auth.html", registering=False, username=username)
        if (
            not isinstance(result, dict)
            or result.get("token_type") != "Bearer"
            or result.get("expires_in") != 28800
            or not isinstance(result.get("token"), str)
            or not TOKEN_PATTERN.fullmatch(result["token"])
        ):
            raise APIError(503, "Réponse de connexion invalide.")
        session.clear()
        response = redirect(url_for("accounts.profile"), code=303)
        response.set_cookie(
            COOKIE,
            result["token"],
            max_age=28800,
            path="/",
            secure=current_app.config["SESSION_COOKIE_SECURE"],
            httponly=True,
            samesite="Lax",
        )
        return response
    return render_template("account_auth.html", registering=False, username="")


@bp.post("/deconnexion")
def logout():
    if token():
        try:
            api().logout(token())
        except APIError as exc:
            if exc.status != 401:
                raise
    return clear_auth(redirect(url_for("accounts.login"), code=303))


@bp.route("/profil", methods=["GET", "POST"])
@signed_in
def profile():
    if request.method == "POST":
        try:
            api().update_profile(token(), {"display_name": request.form.get("display_name", "")})
        except APIError as exc:
            return account_error(exc, "account_profile.html")
        flash("Profil enregistré.")
        return redirect(url_for("accounts.profile"), code=303)
    return render_template("account_profile.html")


@bp.post("/profil/mot-de-passe")
@signed_in
def password():
    if request.form.get("new_password") != request.form.get("password_confirmation"):
        return render_template(
            "account_profile.html", message="Les nouveaux mots de passe ne correspondent pas."
        ), 422
    try:
        api().change_password(
            token(),
            {
                "current_password": request.form.get("current_password", ""),
                "new_password": request.form.get("new_password", ""),
            },
        )
    except APIError as exc:
        return account_error(exc, "account_profile.html")
    return clear_auth(redirect(url_for("accounts.login"), code=303))


@bp.get("/administration")
@signed_in
def administration():
    if g.user["role"] != "admin":
        abort(403)
    offset = request.args.get("offset", "0")
    if not offset.isdecimal() or not 0 <= int(offset) <= 10000:
        abort(422)
    return render_template("account_admin.html", accounts=api().users(token(), int(offset)))


@bp.post("/administration/utilisateurs/<user_id>")
@signed_in
def admin_update(user_id):
    if g.user["role"] != "admin":
        abort(403)
    if (
        set(request.form) != {"csrf_token", "role", "enabled"}
        or request.form["enabled"] not in ("true", "false")
        or request.form["role"] not in ("member", "manager", "admin")
    ):
        abort(422)
    try:
        api().update_user(
            token(),
            user_id,
            {"role": request.form["role"], "enabled": request.form["enabled"] == "true"},
        )
    except APIError as exc:
        if exc.status == 409:
            flash("Le dernier administrateur actif doit être conservé.")
            return redirect(url_for("accounts.administration"), code=303)
        raise
    flash("Compte mis à jour. Ses sessions ont été révoquées si ses droits ont changé.")
    return redirect(url_for("accounts.administration"), code=303)


def install_accounts(app):
    app.register_blueprint(bp)

    @app.before_request
    def load_identity():
        g.user = None
        g.clear_auth_cookie = False
        if (
            request.endpoint in ("static", "pages.health", "accounts.login", "accounts.register")
            or not token()
        ):
            return
        if not TOKEN_PATTERN.fullmatch(token()):
            g.clear_auth_cookie = True
            return
        try:
            g.user = api().me(token())
        except APIError as exc:
            if exc.status == 401:
                g.clear_auth_cookie = True
            else:
                raise

    @app.after_request
    def account_headers(response):
        if (
            (request.endpoint and request.endpoint.startswith("accounts."))
            or g.get("user")
            or token()
        ):
            response.headers["Cache-Control"] = "no-store"
        if g.get("clear_auth_cookie"):
            clear_auth(response)
        return response
