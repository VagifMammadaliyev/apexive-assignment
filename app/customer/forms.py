from django import forms

from customer.models import Balance
from fulfillment.models import Transaction


class AdminBalanceUpdateForm(forms.Form):
    balance = forms.ModelChoiceField(Balance.objects.all())
    amount = forms.DecimalField(
        max_digits=5, decimal_places=2, max_value=1000, min_value=0
    )
    purpose = forms.ChoiceField(
        choices=[
            (Transaction.BALANCE_INCREASE, "Increase balance"),
            (Transaction.BALANCE_DECREASE, "Decrease balance"),
        ]
    )

    def __init__(self, *args, **kwargs):
        user_pk = kwargs.pop("user_pk", None)
        super().__init__(*args, **kwargs)
        self.fields["balance"].queryset = Balance.objects.filter(user_id=user_pk)
