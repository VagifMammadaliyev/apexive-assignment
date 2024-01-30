from django import forms
from django.utils.html import mark_safe

from fulfillment.models import Shipment


class AdminShipmentForm(forms.ModelForm):
    RECALC_HELP_TEXT = mark_safe(
        '<b style="color: orange; font-weight: bold">'
        "Checking this field will trigger total price recalculation!</br>"
        "This will also update related non deleted transaction and recalculate declared price.<br>"
        "Note: Updating transaction's amount will result in updating all 'PROMO CODE'"
        "cashbacks. So be careful!"
        "</b>"
    )

    recalculate_total_price = forms.BooleanField(
        required=False, help_text=RECALC_HELP_TEXT
    )

    class Meta:
        model = Shipment
        fields = "__all__"

    def save(self, *args, **kwargs):
        must_recalculate = self.cleaned_data.pop("recalculate_total_price", False)
        if self.instance and self.instance.pk:
            self.instance._must_recalculate = must_recalculate
            self.instance._update_declared_price = must_recalculate
            self.instance.declared_items_title = (
                self.instance.generate_declared_items_title()
            )
        return super().save(*args, **kwargs)
