import base64
import hmac
import hashlib
import datetime

from django.conf import settings

from cybersource import exceptions as errors


class Security:
    SECRET_KEY = settings.CYBERSOURCE_SECRET_KEY

    def check(self, params: dict):
        provided_signature = params.pop("signature")
        calculated_signature = self._sign(
            self._build_data_to_sign(params).encode(), self.SECRET_KEY.encode()
        )
        return provided_signature == calculated_signature

    def sign(self, params: dict):
        """Signs params using SECRET_KEY"""
        # Add necessary signed_date_time, signed_field_names and unsigned_field_names
        params["signed_date_time"] = (
            str(datetime.datetime.utcnow().isoformat(timespec="seconds")) + "Z"
        )
        params["unsigned_field_names"] = ""
        params["signed_field_names"] = ",".join(
            list(params.keys()) + ["signed_field_names"]
        )

        return self._sign(
            self._build_data_to_sign(params).encode(), self.SECRET_KEY.encode()
        )

    def _sign(self, data, secret_key):
        """Returns signature data using secret_key"""
        return base64.b64encode(
            hmac.new(key=secret_key, msg=data, digestmod=hashlib.sha256).digest()
        ).decode()

    def _build_data_to_sign(self, params: dict):
        """
        Builds string out of a params dictionary in order to sign with secret key.
        """
        try:
            return ",".join(
                [
                    "%s=%s" % (signed_field_name, params[signed_field_name])
                    for signed_field_name in params["signed_field_names"].split(",")
                ]
            )
        except KeyError:
            raise errors.InvalidFormDataError
