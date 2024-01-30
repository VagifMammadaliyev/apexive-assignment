import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

import requests
import extruct
from rest_framework import status
from django.conf import settings
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

from core.models import Country, OnlineShoppingDomain
from core.converter import Converter


class AutoFiller:
    def __init__(self, order=None, product_url=None):
        self.related_order = order
        if not product_url and order:
            product_url = order.product_url
        if not product_url:
            self._fail()
        if not product_url.startswith("http"):
            product_url = f"http://{product_url}"
        self.product_url = product_url
        self.user_agent = UserAgent().random

    def _fail(self, override_status=None):
        return {
            "country": None,
            "description": None,
            "price": None,
            "color": None,
            "image": None,
            "raw": {},
        }, status.HTTP_200_OK

    def save_image_to_order(self, order=None):
        data, _ = self.fetch()
        order = order or self.related_order
        if not order:
            return False

        order.product_image_url = data.get("image")
        order._fetch_image = False
        order.save(update_fields=["product_image_url"])
        return True

    def get_country(self):
        # At this point product_url is a valid URL.
        # Try to get the source country from top-level domain.
        # If it is not possible try to fetch from DB.
        # We already added domain -> country mappings.
        parse_result = urlparse(self.product_url)
        netloc = parse_result.netloc

        # Get rid of port
        port = parse_result.port
        if port:
            netloc = netloc.replace(f":{port}", "")

        splitted_netloc = netloc.split(".")
        if splitted_netloc:
            top_level_domain = splitted_netloc[-1]

            try:
                # Try to get from active countries
                country = Country.objects.filter(is_active=True).get(
                    code__iexact=top_level_domain
                )
                return country
            except Country.DoesNotExist:
                pass

        # Try to get from domain name saved in DB
        # Note: We can't get exactly the domain level we need
        # Imagine this: www.a.b.c.d.com
        # How do we now if "b" is what we need?
        saved_domains = OnlineShoppingDomain.objects.filter(
            country__is_active=True
        ).values("domain", "country_id")

        for saved_domain in saved_domains:
            if saved_domain["domain"] in netloc:
                return Country.objects.get(id=saved_domain["country_id"])

        return None

    def get_country_serializer(self):
        from core.serializers.client import CountryCompactWithCurrencySerializer

        return CountryCompactWithCurrencySerializer

    def get_serialized_country(self, country=None):
        serializer = self.get_country_serializer()
        return serializer(country or self.get_country()).data

    def extract_product_description(self, data):
        for syntax in self.get_syntaxes(data):
            description = self._extract_product_description_from(syntax)
            if description:
                to_be_replaced = [
                    "details about",
                    "details",
                    "description",
                    "description about",
                    "about",
                ]

                for phrase in to_be_replaced:
                    insensetive_phrase = re.compile(re.escape(phrase), re.IGNORECASE)
                    description = str(insensetive_phrase.sub("", description))
                return description.strip()

        return None

    def _extract_product_description_from(self, data):
        for item in data:
            if self._check_info_type(item):
                name = item.get("name")
                description = item.get("description")

                if name and isinstance(name, (list, tuple)):
                    return name[0]

                if name and isinstance(name, str):
                    return name

                if not name:
                    return description

                return name

        return None

    def extract_product_price_currency_code(self, data):
        for syntax in self.get_syntaxes(data):
            product_price_currency = self._extract_product_price_currency_code_from(
                syntax
            )
            if product_price_currency:
                return product_price_currency

        return None

    def _check_info_type(self, item, target_type="product"):
        item_type = item.get("@type", None)

        if isinstance(item_type, (list, tuple)):
            for _item_type in item_type:
                if _item_type.lower() == target_type.lower():
                    return True

        else:
            if item_type:
                return item_type.lower() == target_type.lower()

        return False

    def _extract_product_price_from(self, data):
        for item in data:
            if self._check_info_type(item):
                price = None
                offers = item.get("offers", None)

                if isinstance(offers, dict):
                    price = offers.get("price") or offers.get("lowPrice")

                elif isinstance(offers, list):
                    for offer in offers:
                        price = offer.get("price") or offer.get("lowPrice")
                        if price:
                            break

                if not price:
                    price = item.get("price")

                if price:
                    try:
                        return str(round(Decimal(price), 2))
                    except InvalidOperation:
                        price_matches = re.findall(r"([,\d]+.?\d*)", price)
                        if price_matches:
                            price_str: str = price_matches[0]
                            price_str = price_str.replace(",", ".")
                            return str(round(Decimal(price_str), 2))

        return None

    def _extract_product_price_currency_code_from(self, data):
        for item in data:
            if self._check_info_type(item):
                price_currency = None
                offers = item.get("offers", None)

                if isinstance(offers, dict):
                    price_currency = offers.get("priceCurrency")

                elif isinstance(offers, list):
                    for offer in offers:
                        price_currency = offer.get("priceCurrency", None)
                        if price_currency:
                            break

                if not price_currency:
                    price_currency = item.get("priceCurrency")

                if price_currency:
                    return price_currency

        return None

    def _extract_product_color_from(self, data):
        for item in data:
            if self._check_info_type(item):
                color = item.get("color")

                if color:
                    return color

        return None

    def get_syntaxes(self, data):
        json_ld = data.get("json-ld")
        microdata = data.get("microdata")
        microformat = data.get("microformat")

        return [json_ld, microdata, microformat]

    def extract_product_price(self, data):
        for syntax in self.get_syntaxes(data):
            product_price = self._extract_product_price_from(syntax)
            if product_price:
                return product_price

        return None

    def extract_product_color(self, data):
        for syntax in self.get_syntaxes(data):
            product_color = self._extract_product_color_from(syntax)
            if product_color:
                return product_color

        return None

    def _normalize_image_url(self, image_url):
        if image_url.count("http") > 1:
            image_urls = image_url.split(",")
            return image_urls[0]
        return image_url

    def _extract_product_image_from(self, data):
        for item in data:
            if self._check_info_type(item):
                image = item.get("image")

                if isinstance(image, list):
                    for _image in image:
                        _image = self._normalize_image_url(_image)
                        if _image:
                            return _image
                elif isinstance(image, str):
                    return self._normalize_image_url(image)

        return None

    def extract_product_image(self, data):
        for syntax in self.get_syntaxes(data):
            product_image = self._extract_product_image_from(syntax)
            if product_image:
                return product_image

        return None

    def fetch(self):
        try:
            response = requests.get(
                self.product_url, headers={"User-Agent": self.user_agent}
            )
        except requests.exceptions.RequestException:
            return self._fail()

        if response.status_code == status.HTTP_200_OK:
            _country = self.get_country()
            country = None

            data = extruct.extract(
                response.content,
                syntaxes=["json-ld", "microdata", "microformat"],
                uniform=True,
            )
            price_currency = self.extract_product_price_currency_code(data)

            if not _country:
                # The try to get price currency for this product
                # and deduct country from it.
                matching_countries = Country.objects.filter(
                    is_active=True, currency__code__iexact=price_currency
                )
                if len(matching_countries) == 1:
                    _country = matching_countries[0]

            product_price = None

            if _country:
                country = self.get_serialized_country(country=_country)

                product_price = self.extract_product_price(data)
                if product_price:
                    from core.models import Currency

                    try:
                        product_price = str(
                            Converter.convert(
                                product_price, price_currency, _country.currency.code
                            )
                        )
                    except Currency.DoesNotExist:
                        pass

            data = {
                "country": country,
                "description": self.extract_product_description(data),
                "price": product_price,
                "color": self.extract_product_color(data),
                "image": self.extract_product_image(data),
                "raw": data if settings.DEBUG else None,
            }

            return data, status.HTTP_200_OK
        return self._fail(override_status=response.status_code)
