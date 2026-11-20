from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import SMSForm
from .models import SMSLog
from .services import SMSError, fetch_status, send_sms


def send_sms_view(request):
    if request.method == "POST":
        form = SMSForm(request.POST)
        if form.is_valid():
            to = form.cleaned_data["recipient"]
            body = form.cleaned_data["message"]
            try:
                result = send_sms(to, body)
            except SMSError as exc:
                SMSLog.objects.create(
                    recipient=to,
                    body=body,
                    status=SMSLog.FAILED,
                    error_message=exc.user_message[:300],
                )
                messages.error(request, exc.user_message)
            else:
                SMSLog.objects.create(
                    recipient=to, body=body, status=result.status, provider_sid=result.sid
                )
                # "Submitted" is not "delivered": the gateway has only accepted it.
                messages.success(
                    request,
                    f"Message submitted to the SMS gateway (status: {result.status}). "
                    "Your phone still has to send it, and delivery isn't confirmed yet. "
                    "Check History for updates.",
                )
                return redirect("send_sms")  # Post/Redirect/Get avoids double sends
    else:
        form = SMSForm()
    return render(request, "sms_app/send.html", {"form": form})


def history_view(request):
    logs = SMSLog.objects.all()[:50]
    return render(request, "sms_app/history.html", {"logs": logs})


@require_POST
def refresh_status_view(request, pk):
    log = get_object_or_404(SMSLog, pk=pk)
    if not log.provider_sid:
        messages.error(request, "This message was never submitted, so it has no status to check.")
        return redirect("history")
    try:
        log.status = fetch_status(log.provider_sid)
        log.save(update_fields=["status", "updated_at"])
    except SMSError as exc:
        messages.error(request, exc.user_message)
    else:
        messages.info(request, f"Status for {log.recipient}: {log.status}.")
    return redirect("history")
