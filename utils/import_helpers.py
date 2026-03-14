import csv
import io
from django.http import HttpResponse


def parse_csv(uploaded_file):
    """
    Parse an uploaded CSV file and return (headers, rows).
    Handles UTF-8 BOM that Excel adds.
    """
    content = uploaded_file.read().decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(content))
    headers = reader.fieldnames or []
    rows = list(reader)
    return headers, rows


def sample_csv_response(filename, headers):
    """Return an empty CSV with just the header row as a downloadable template."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(headers)
    return response
