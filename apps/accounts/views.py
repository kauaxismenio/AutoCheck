from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render

from apps.core.audit import log_action

from .forms import LoginForm


class AutoCheckLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action("accounts.login", request=self.request, user=form.get_user())
        return response


class AutoCheckLogoutView(LogoutView):
    http_method_names = ["post", "options"]


@login_required
def change_own_password(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        log_action("accounts.password_changed", request=request, obj=user)
        messages.success(request, "Senha alterada.")
        return redirect("core:home")
    return render(request, "accounts/password_form.html", {"form": form, "title": "Alterar minha senha"})
