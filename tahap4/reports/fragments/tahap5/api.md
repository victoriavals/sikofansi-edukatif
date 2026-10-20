#### komersial_A

| Panggilan | n | Latensi rata-rata / median (s) | Token input | Token output | Token penalaran rata-rata (maks.) | Ada teks penalaran | finish | Biaya pengaman ($) | Biaya dari API ($) |
|---|---|---|---|---|---|---|---|---|---|
| G0 | 180 | 1.7 / 1.5 | 43 | 30 | 19 (128) | 0 | stop=180 | 0.0035 | 0.0035 |
| dialog G1 | 1080 | 2.5 / 2.3 | 58 | 109 | 35 (127) | 0 | stop=1080 | 0.0653 | 0.0653 |
| dialog G2 | 1080 | 3.0 / 2.8 | 154 | 160 | 57 (326) | 0 | stop=1080 | 0.1032 | 0.1032 |
| dialog G3 | 1080 | 2.5 / 2.3 | 276 | 115 | 40 (190) | 0 | stop=1080 | 0.0920 | 0.0920 |

ID respons: 3420 unik dari 3420 panggilan; field `model`: gpt-6-luna; header hulu: `x-litellm-model-api-base` = https://api-sg.umodelverse.ai/v1; `x-litellm-model-name` = gpt-6-luna.

#### komersial_B

| Panggilan | n | Latensi rata-rata / median (s) | Token input | Token output | Token penalaran rata-rata (maks.) | Ada teks penalaran | finish | Biaya pengaman ($) | Biaya dari API ($) |
|---|---|---|---|---|---|---|---|---|---|
| G0 | 180 | 1.7 / 1.2 | 42 | 121 | 118 (1016) | 180 | stop=180 | 0.0128 | 0.0128 |
| dialog G1 | 1080 | 4.4 / 3.8 | 58 | 486 | 256 (1226) | 1080 | stop=1080 | 0.2781 | 0.2781 |
| dialog G2 | 1080 | 11.1 / 10.5 | 313 | 1232 | 737 (2676) | 1080 | stop=1080 | 0.7500 | 0.7500 |
| dialog G3 | 1080 | 9.6 / 9.0 | 831 | 998 | 539 (1599) | 1080 | stop=1080 | 0.7635 | 0.7382 |

ID respons: 3420 unik dari 3420 panggilan; field `model`: deepseek-v4-flash-0731:netra; header hulu: `x-litellm-model-api-base` = https://api.netraruntime.com/v1; `x-litellm-model-name` = deepseek/deepseek/deepseek-v4-flash-0731.