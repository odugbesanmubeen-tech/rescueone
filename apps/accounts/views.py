from django.contrib.auth.views import LoginView
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

from apps.audit.services import log as audit_log

from .forms import OpsAuthenticationForm


@method_decorator(ratelimit(key="ip", rate="10/m", method="POST", block=True), name="post")
class OpsLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = OpsAuthenticationForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        audit_log(self.request.user, "login", request=self.request)
        return response
