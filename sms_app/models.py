from django.db import models


class SMSLog(models.Model):
    """One sending attempt. `status` is the gateway's state, or 'failed' if we never got one."""

    FAILED = "failed"
    FINAL_STATUSES = {"delivered", "undelivered", "failed"}

    recipient = models.CharField(max_length=20)
    body = models.TextField()
    status = models.CharField(max_length=20)
    provider_sid = models.CharField(max_length=64, blank=True)
    error_message = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.recipient} ({self.status})"

    @property
    def can_refresh(self):
        """Only messages the gateway accepted, and that haven't reached a final state."""
        return bool(self.provider_sid) and self.status not in self.FINAL_STATUSES
