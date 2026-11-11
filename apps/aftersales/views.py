from datetime import datetime, time

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import urlencode

from apps.attendances import workflow as wf
from apps.attendances.models import Attendance
from apps.attendances.views import search_attendances

from . import services


def _day_bound(value, end=False):
    day = parse_date(value or "") if value else None
    if day is None:
        return None
    return timezone.make_aware(datetime.combine(day, time.max if end else time.min))


@login_required
def aftersales_list(request):
    term = request.GET.get("q", "")
    start, end = request.GET.get("de", ""), request.GET.get("ate", "")
    only_pending = request.GET.get("pendentes") == "1"

    queryset = Attendance.objects.filter(status=wf.STATUS_CONCLUIDO).select_related(
        "customer", "vehicle",
    ).prefetch_related("services", "replacements").order_by("-completed_at")
    queryset = search_attendances(queryset, term)
    start_bound, end_bound = _day_bound(start), _day_bound(end, end=True)
    if start_bound:
        queryset = queryset.filter(completed_at__gte=start_bound)
    if end_bound:
        queryset = queryset.filter(completed_at__lte=end_bound)
    if only_pending:
        queryset = services.with_pending_recommendations(queryset)

    page = Paginator(queryset, 20).get_page(request.GET.get("pagina"))
    return render(request, "aftersales/list.html", {
        "page": page, "rows": [services.describe(att) for att in page.object_list],
        "q": term, "start": start, "end": end, "only_pending": only_pending,
        "query_string": urlencode({"q": term, "de": start, "ate": end, "pendentes": "1" if only_pending else ""}),
    })
