from django import forms


class SimpleCalculatorForm(forms.Form):
    COUNTRY_CHOICES = [(value, value) for value in ("US", "AU", "GB", "EU", "Other")]

    sale_price_usd = forms.DecimalField(label="販売価格USD", max_digits=12, decimal_places=2)
    shipping_received_usd = forms.DecimalField(label="送料受取USD", max_digits=12, decimal_places=2, initial=0)
    country = forms.ChoiceField(label="販売国", choices=COUNTRY_CHOICES, initial="US")
    purchase_price_yen = forms.DecimalField(label="仕入価格円", max_digits=14, decimal_places=2)
    domestic_shipping_yen = forms.DecimalField(label="国内送料円", max_digits=14, decimal_places=2, initial=0)
    exchange_rate = forms.DecimalField(label="使用為替", max_digits=10, decimal_places=4, initial=155, min_value=0.0001)
    ebay_fvf_rate = forms.DecimalField(label="eBay FVF率", max_digits=7, decimal_places=3, initial=13.25)
    international_fee_rate = forms.DecimalField(label="海外手数料率", max_digits=7, decimal_places=3, initial=1.35)
    ad_rate = forms.DecimalField(label="広告率", max_digits=7, decimal_places=3, initial=2)
    parcel_shipping_yen = forms.DecimalField(label="荷物分送料円", max_digits=14, decimal_places=2, initial=3500)
    sales_tax_rate = forms.DecimalField(label="Sales Tax率", max_digits=7, decimal_places=3, initial=8)

    def clean(self):
        cleaned = super().clean()
        sale = cleaned.get("sale_price_usd")
        shipping = cleaned.get("shipping_received_usd")
        rate = cleaned.get("exchange_rate")
        if sale is not None and shipping is not None and rate is not None and (sale + shipping) * rate <= 0:
            raise forms.ValidationError("売上円は0より大きい値になるよう入力してください。")
        return cleaned

