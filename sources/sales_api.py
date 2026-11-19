"""Sales orders from an explicitly compatible public HTTPS JSON endpoint."""
from core.exceptions import DataValidationError
from sources.api_reader import ApiTaskReader
from sources.base import SourceData, read_boundary
from sources.csv_excel import normalize_rows


class ApiSalesReader(ApiTaskReader):
    api_label = "Sales"
    def __init__(self, url, client=None, timeout=10.0):
        super().__init__(client=client, timeout=timeout, url=url)

    def read(self) -> SourceData:
        with read_boundary('Sales REST API'):
            payload = self.fetch_payload()
            if not isinstance(payload, list) or not payload:
                raise DataValidationError('Sales API must return a nonempty JSON array of sales order objects; cart envelopes are not supported.')
            orders = []
            for number, record in enumerate(payload, 1):
                if not isinstance(record, dict):
                    raise DataValidationError('Sales API record {} must be an object.'.format(number))
                with read_boundary('Sales API record {}'.format(number)):
                    orders.extend(normalize_rows([list(record), list(record.values())]).orders)
            return SourceData(orders=orders)
