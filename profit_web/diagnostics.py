from django.db import connection
from django.http import HttpResponse

from . import views
from .models import EbayConnection, EbayOrderLine, MonthlyExchangeRate


def _plain(message, status):
    return HttpResponse(message, status=status, content_type="text/plain; charset=utf-8")


def monthly_with_db_diagnostic(request):
    """Temporary production diagnostic for the monthly page.

    It intentionally exposes only coarse status codes and known Django table names;
    no connection string, credentials, SQL, or exception message is returned.
    """
    expected_tables = {
        EbayConnection._meta.db_table,
        EbayOrderLine._meta.db_table,
        MonthlyExchangeRate._meta.db_table,
    }

    try:
        existing_tables = set(connection.introspection.table_names())
    except Exception as exc:
        return _plain(
            f"MONTHLY_DIAG:DATABASE_ERROR:{exc.__class__.__name__}",
            status=503,
        )

    missing_tables = sorted(expected_tables - existing_tables)
    if missing_tables:
        return _plain(
            "MONTHLY_DIAG:MIGRATIONS_MISSING:" + ",".join(missing_tables),
            status=503,
        )

    try:
        return views.monthly(request)
    except Exception as exc:
        return _plain(
            f"MONTHLY_DIAG:RUNTIME_ERROR:{exc.__class__.__name__}",
            status=500,
        )
