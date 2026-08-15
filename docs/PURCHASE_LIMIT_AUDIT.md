# Purchase-limit business assumption audit

## Superseded integration assumption

この監査で使用した「SKU Master の ×1.15 値を shipping-included selling TOTAL cap
として渡す」という integration 前提は、既存 Pricing Tool GUI との照合により SKU
Master 用途では誤りと判明した。8,858 JPY という数値分析自体は、generic な
`max_purchase_yen_for_selling_total()` の contract 監査として引き続き有効である。

SKU Master では今後、×1.15 値を送料・duty を含まない `product_price_usd` として扱い、
`max_purchase_yen_for_product_price()` を使用する。以下は当時の前提とその計算結果を
歴史的な監査記録として維持する。

## 1. 現在の business contract

この監査は SKU Master の shipping-included `allowed_selling_total_usd` をそのまま
Pricing Core に渡す契約を前提とする。eBay 最安 TOTAL 102.60 USD に 1.15 を掛けた
117.99 USD は **product price ではなく selling TOTAL の上限**である。現行 resolver は
この上限を product price 99.99 USD と duty/shipping 18.00 USD に解決する。

購入上限 API は `gross_profit_yen >= 0` となる最大の整数円を返す。refund profit は
表示用の別指標であり、購入上限の判定には使われない。本監査はこの意味、1.15 の意味、
Settings の既定値、およびすべての production formula を変更しない。

## 2. CURRENT: 117.99 USD から 8,858 JPY への waterfall

条件は `Settings()`、FX 155 JPY/USD、package shipping 3,000 JPY である。表示値は
追跡可能性のため丸めているが、上限探索は float の計算結果を使用する。

| 項目 | 計算 | JPY |
|---|---:|---:|
| resolved product price | 99.99 USD | — |
| duty/shipping | 18.00 USD | — |
| selling TOTAL | 117.99 USD | — |
| sales | 117.99 × 155 | 18,288.450 |
| sales-tax-included fee base | 18,288.450 × 1.08 | 19,751.526 |
| eBay FVF | 19,751.526 × 13.25% + 0.40 × 155 | -2,679.077 |
| international fee | 19,751.526 × 1.35% | -266.646 |
| ad fee | 19,751.526 × 2% | -395.031 |
| Payoneer | (sales − 上記3 fee) × 2% | -298.954 |
| **total fees** | | **-3,639.707** |
| package shipping | | -3,000.000 |
| duty/shipping converted to JPY | 18.00 × 155 | -2,790.000 |
| **total shipping** | | **-5,790.000** |
| other cost | | 0.000 |
| **仕入前の残額** | 18,288.450 − 3,639.707 − 5,790 | **8,858.743** |
| **gross break-even max purchase** | 最大整数円 | **8,858** |

上限での gross profit は **+0.742750 JPY**、8,859 JPY 仕入時は
**-0.257250 JPY**であり、整数境界を満たす。

## 3. Scenario matrix

`difference_vs_8858` は常に Golden の 8,858 JPY との差である。refund 行も
production API の結果ではなく、監査 helper が既存 `calculate_metrics()` の
`refund_profit_yen >= 0` 境界を探索した結果である。

| Scenario | Basis | FX | Package shipping | Max purchase | Difference vs 8,858 | Notes |
|---|---|---:|---:|---:|---:|---|
| A CURRENT | gross | 155.00 | 3,000 | **8,858** | 0 | production contract |
| B | gross | 159.31 | 3,000 | **9,188** | +330 | FX sensitivity |
| C | gross | 159.31 | 3,500 | **8,688** | -170 | B より送料 +500 |
| D | refund | 155.00 | 3,000 | **10,038** | +1,180 | audit only |
| E | refund | 159.31 | 3,000 | **10,409** | +1,551 | audit only; 10,500 に最接近 |
| F | refund | 159.31 | 3,500 | **9,859** | +1,001 | audit only |
| H1 | gross | 155.00 | 3,000 | **11,648** | +2,790 | **HYPOTHETICAL ONLY:** duty/shipping JPY cost を除外 |
| H2 | gross | 155.00 | 3,000 | **9,096** | +238 | **HYPOTHETICAL ONLY:** sales-tax uplift を fee base から除外 |
| H3 | gross | 159.31 | 3,000 | **12,056** | +3,198 | **HYPOTHETICAL ONLY:** duty/shipping JPY cost を除外 |
| H4 | gross | 159.31 | 3,000 | **9,433** | +575 | **HYPOTHETICAL ONLY:** tax uplift 除外（同 FX の B 比 +245） |

各整数境界では選択 basis の profit が 0 以上で、次の 1 円では負になる。個別効果は
丸めと refund 式中の purchase-dependent adjustment のため、異なる基準から得た差を
単純合算してはならない。

## 4. Gross と refund、および 10,500 JPY gap

CURRENT の 8,858 から運用感覚 10,500 までは **+1,642 JPY**である。

| 前提変更（他は CURRENT 固定） | 上限 | CURRENT からの移動 | 残る 10,500 gap |
|---|---:|---:|---:|
| FX 155 → 159.31 (gross) | 9,188 | +330 | 1,312 |
| gross → refund basis (FX 155) | 10,038 | +1,180 | 462 |
| package shipping 3,000 → 3,500 (gross) | 8,358 | -500 | 2,142 |
| duty/shipping cost を除外 | 11,648 | +2,790 | -1,148 (超過) |
| sales-tax fee-base uplift を除外 | 9,096 | +238 | 1,404 |

refund basis と FX 159.31 を同時に用いる Scenario E は **10,409 JPY**で、今回の
比較中では 10,500 に最も近く、差は -91 JPY である。これは「10,500 感覚」が
還付込み損益分岐と、より高い実運用 FX の組合せに近いことを示すが、その basis を
採用すべきだという結論ではない。

Package shipping だけで gross 上限を 10,500 にするには、CURRENT の 3,000 JPY
から約 **1,358 JPY**へ下げる必要がある（整数上限が 10,500 となる範囲は
1,357.743 JPY 超、1,358.743 JPY 以下）。これは calibration の提案ではなく、
差 1 円が上限 1 円に直結することを示す逆算である。

## 5. 原因となる business assumptions

1. **利益定義:** gross は還付を一切使わない。refund 式には仕入の 9.09% と、FVF・
   international fee に関する還付調整が入り、CURRENT で上限を 1,180 JPY 押し上げる。
2. **duty/shipping の二つの役割:** 18 USD は selling price に含まれて sales を作る一方、
   `18 × FX` が package shipping に加算される。CURRENT の cost は 2,790 JPY。
   H1 は後者だけを除いた仮説で、**CURRENT formula は両方を行う**。
3. **fee base:** sales-tax uplift は sales 18,288.450 JPY を 19,751.526 JPY にしてから
   FVF、international、ad を計算する。Payoneer も先行 fee の変化を受ける。uplift の
   正味 fee 影響は CURRENT で **238.013 JPY**（整数上限差 +238）。
4. **FX:** 売上と USD 固定 fee、duty/shipping cost の双方に効くため、単なる売上だけの
   比例変更ではない。155 → 159.31 は gross で +330、refund で +371（D → E）。
5. **package shipping:** JPY 固定控除なので gross では 500 JPY 増が上限を正確に
   500 JPY下げる。refund は仕入額依存の還付項があるため D/E から F への差は異なる。

## 6. 次PRで検討できる Option（今回は実装しない）

| Option | 10,500 への近さ | GUI / SKU Master / 過去結果 | Business meaning |
|---|---|---|---|
| A. gross basis 維持、Settings を実運用値へ | FX 159.31 のみでは 9,188。送料だけなら約1,358が必要で、根拠の検証が必要 | GUI と過去結果は Settings 変更分だけ変化。SKU Master の TOTAL semantic/API は不変 | 保守的な gross 損益分岐を維持し、観測可能なコスト・FXだけ更新 |
| B. refund basis を購入上限に採用 | FX 155で10,038、159.31で10,409（-91） | GUI・過去の全 purchase limit が上昇し得る。SKU Master の入力/API形状は不変でも返値が変化 | 還付の実現可能性・時期・対象範囲を仕入判断に織り込む |
| C. duty/shipping treatment を再定義 | cost 除外だけでは11,648となり +1,148 超過 | GUI・過去結果へ大きな影響。SKU Master と「TOTAL」「duty/shipping」の責任分界を再合意要 | 買い手徴収 shipping が実コストを相殺するのか、二重計上なのかを会計事実から決定 |
| D. fee-base の tax treatment を再確認 | uplift 除外でも9,096で、単独では不足 | fee 対象全価格帯と過去結果に中程度の影響。SKU Master 入力は不変 | eBay の実際の fee 明細で tax を fee base に含める契約・地域条件を検証 |

## 7. 次PRで決めるべき一点

購入可能額を **回収確度の高い gross basis** と **将来の還付を織り込む refund basis** の
どちらで意思決定するかを、実際の還付証憑とリスク許容度に基づいて決める。その決定前に
FX や送料を目標値へ逆算して混ぜない。duty/shipping と tax fee-base は請求明細との照合を
別途行い、契約 semantic を先に確定する。

**10,500という目標値に合わせるためだけの calibration は行っていない。**
