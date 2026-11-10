def user_can_view_incident_files(user, incident):
    """Ops, the reporting citizen, or a responder who was offered/assigned the incident."""
    return bool(
        user.is_ops
        or incident.citizen_id == user.pk
        or incident.assignments.filter(responder__user=user, status__in=["OFFERED", "ACCEPTED", "COMPLETED"]).exists()
    )
