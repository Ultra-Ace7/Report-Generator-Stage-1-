"""Explicit external sales headers mapped to the internal business contract."""
import re

from core.exceptions import DataValidationError

FIELD_ALIASES = {
    'order_id': ('Order ID', 'Order Number', 'Transaction ID'),
    'order_date': ('Date', 'Order Date', 'Transaction Date'),
    'customer': ('Customer', 'Customer Name', 'Client', 'Client Name'),
    'service': ('Service', 'Service Type', 'Product'),
    'revenue': ('Revenue', 'Sales Amount', 'Amount', 'Total Amount'),
    'currency': ('Currency', 'Currency Code'),
}
COLUMNS = tuple(FIELD_ALIASES)


def normalize_header(value):
    return re.sub(r'[\s_-]+', ' ', value.strip().casefold()) if isinstance(value, str) else ''


HEADER_FIELDS = {normalize_header(alias): field
                 for field, aliases in FIELD_ALIASES.items()
                 for alias in (field,) + aliases}
AMBIGUOUS_REVENUE_HEADERS = {'amount', 'total amount'}
ADJUSTMENT_WORDS = {'tax', 'taxes', 'gst', 'vat', 'refund', 'refunds', 'discount', 'discounts'}


def map_sales_header(header):
    """Return canonical names by input index; None marks unrelated columns."""
    normalized = [normalize_header(value) for value in header]
    mapped = [HEADER_FIELDS.get(value) for value in normalized]
    for field in COLUMNS:
        conflicts = [str(header[i]) for i, name in enumerate(mapped) if name == field]
        if len(conflicts) > 1:
            raise DataValidationError("Multiple columns map to '{}': {}. Please keep only one.".format(field, ', '.join(conflicts)))
    missing = [field for field in COLUMNS if field not in mapped]
    if missing:
        hints = ' '.join('Accepted {} columns include {}.'.format(field, ', '.join(FIELD_ALIASES[field])) for field in missing)
        raise DataValidationError('Missing required sales fields: {}. {}'.format(', '.join(missing), hints))
    revenue_index = mapped.index('revenue')
    adjustments = [str(header[i]) for i, name in enumerate(normalized)
                   if ADJUSTMENT_WORDS.intersection(name.split())]
    if normalized[revenue_index] in AMBIGUOUS_REVENUE_HEADERS and adjustments:
        raise DataValidationError("Ambiguous revenue column '{}': adjustment columns {} are present. Supply recognized sales excluding tax as Revenue; do not rename a gross total without verifying its meaning.".format(header[revenue_index], ', '.join(adjustments)))
    return mapped
