from django import forms


class SimpleCalculatorForm(forms.Form):
    domestic_min_yen = forms.DecimalField(label="国内最安値円", max_digits=14, decimal_places=2, min_value=0)
    target_margin_1 = forms.DecimalField(label="目標粗利率1（%）", max_digits=7, decimal_places=2, initial=5)
    target_margin_2 = forms.DecimalField(label="目標粗利率2（%）", max_digits=7, decimal_places=2, initial=10)
    ad_rate = forms.DecimalField(label="広告率（%）", max_digits=7, decimal_places=3, initial=2)
    manual_exchange_rate = forms.DecimalField(
        label="為替手動上書き", max_digits=10, decimal_places=4, min_value=0.0001, required=False
    )
    international_fee_rate = forms.DecimalField(label="海外手数料率（%）", max_digits=7, decimal_places=3, initial=1.35)
    sales_tax_rate = forms.DecimalField(label="Sales Tax率（%）", max_digits=7, decimal_places=3, initial=8)
    package_shipping_yen = forms.DecimalField(label="荷物発送円", max_digits=14, decimal_places=2, initial=3500, min_value=0)
    ebay_fvf_rate = forms.DecimalField(label="eBay FVF率（%）", max_digits=7, decimal_places=3, initial=13.25)

    def clean(self):
        cleaned = super().clean()
        for name in ("target_margin_1", "target_margin_2", "ad_rate", "international_fee_rate", "sales_tax_rate", "ebay_fvf_rate"):
            value = cleaned.get(name)
            if value is not None and not 0 <= value < 100:
                self.add_error(name, "0以上100未満で入力してください。")
        return cleaned
