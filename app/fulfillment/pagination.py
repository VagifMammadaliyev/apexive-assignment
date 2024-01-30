from rest_framework import pagination


class ShoppingAssistantPagination(pagination.PageNumberPagination):
    max_page_size = 5


class DynamicPagination(pagination.PageNumberPagination):
    page_size_query_param = "limit"
