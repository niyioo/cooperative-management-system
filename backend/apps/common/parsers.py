"""
Request parsers. The API accepts JSON only (REST_FRAMEWORK.DEFAULT_PARSER_CLASSES);
views that receive files use UPLOAD_PARSERS instead.
"""
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

UPLOAD_PARSERS = (MultiPartParser, FormParser, JSONParser)
