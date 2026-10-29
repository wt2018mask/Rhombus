# 0193 원문 확보 및 파서 점검 — 2026-10-28

**결론: 두 원문 모두 이번에 확보하거나 재인증하지 못했다. 0193은 REVIEW_BLOCKED다.**
2018·2020의 DOI, 25°C 관련 문장, 시료별 열처리 및 전도도는 현재 독립 확인 전인
역사 기록과 소유자 제공 탐색 단서다. 원문 일부나 검색 결과를 새 증거로 취급하지 않는다.
기계 판독용 기록은 [source0193_review_20261028_v1.json](../data/development/source0193_review_20261028_v1.json)이다.

## 접근 및 출처 구분

현재 세션의 강제 HTTP 허용 목록에는 `pubs.rsc.org`, `www.mdpi.com`,
`pmc.ncbi.nlm.nih.gov`, `www.ebi.ac.uk`가 없어 해당 원문 요청을 **시도하지 않았다**.
이는 HTTP 403/429, DNS, TLS 실패를 실제로 관측했다는 뜻이 아니다. 기존 환경 draft의
다른 custom host를 보존하고 세 publisher/PMC host를 추가했으며, 기존 draft에는 Europe PMC와
GitHub API가 이미 있다. 저장은 성공했지만 현재 runtime에 적용되지 않았다. 환경 설정에서
검토·저장하고 publish한 뒤 새 runtime의 실제 허용 상태를 확인해야 한다. 우회 경로를 사용하지 않았다.

| 연도/DOI | 원문 및 요청 경로 | 이번 바이트/해시 | 기존 기록과 남은 확인 |
|---|---|---|---|
| 2018 RSC `10.1039/c8ra01329b` | [출판사 HTML](https://pubs.rsc.org/en/content/articlehtml/2018/ra/c8ra01329b), [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9079727/), Europe PMC `/europepmc/webservices/rest/PMC9079727/fullTextXML` | SOURCE_UNAVAILABLE; 원문 미수집, SHA 없음 | 0196 문서에 JATS SHA `6dee69ef498243cc04c03a4d049175123cfac1b8dfa99257781da76d34979eea`가 **과거 주장**으로 기록됨. Table 1과 3, 온도·단위·시료 대응을 원문 바이트로 재확인해야 함 |
| 2020 Materials `10.3390/ma13030560` | [출판사 HTML](https://www.mdpi.com/1996-1944/13/3/560), [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC7040616/), Europe PMC `/europepmc/webservices/rest/PMC7040616/fullTextXML` | SOURCE_UNAVAILABLE; 원문 미수집, SHA 없음 | 0196 문서의 JATS SHA `51b35a6b942557d1f6cb7ab77d63ca36dbd4d3fbd44a6e44d0ad6f3557392b63`은 과거 주장. Table 2 heading·열·시료·단위를 실제 bytes로 재확인해야 함 |

기록된 0191 run 38899828332와 artifact 12045328896의 ZIP SHA
`1a8f39fbfc82a07baa84b628546c4e76e6d7b12f44ba38de3e3aed368f26172f`은 문서상
과거 정보다. GitHub API artifact 조회는 `Forbidden`이라 보존 상태·원본 bytes·해시를
재확인하지 못했다. Git 저장소의 `process_feature_identifiability_20261021_v1.json`에는
LLZALO-4 1210°C/900분/2.10e-4 S/cm, LLZALO-5 1220°C/600분/1.32e-4 S/cm,
SL1 1200°C/60분/1.58e-4 S/cm, SL2 1200°C/30분/5.09e-4 S/cm이 남아 있다.
이는 역사적 추출값이지 이번 원문 독립 인증이 아니다. 전자의 처리 시간도 다르므로
온도만의 인과 효과로 해석할 수 없다. 298 K와 정확한 25°C(298.15 K)는 구분하고,
저자가 명시한 표현과 실제 측정·fitting 여부를 원문에서 확인해야 한다.

## 검증 코드 개선 및 한계

전방 변경은 0187의 table caption에서 단순 숫자 `25`만 있거나 25 K·125°C·0.25 등인
경우를 거부하고, 명시적 Celsius 표기가 있을 때만 다음 확인으로 진행한다. 2020 값은
샘플 행의 임의 숫자가 아니라 유일한 total conductivity header의 열에서 대조한다.
0188은 `x10^4`를 `x10^-4`로 조용히 해석하던 정규식을 수정해 음수 지수를 요구한다.
각 공격은 합성 변조 fixture로 시험했다. 이 검사는 필요조건일 뿐 출판사·PMC 출처 인증,
25°C 직접 측정, bulk/total 물리적 해석이나 과학적 적격성을 증명하지 않는다. 특히 2018
본문의 단순 `25` 검사는 아직 측정 문맥을 묶지 못한다. 실제 원문의 table 구조와 정밀
문맥이 아직 없어 새 header 규칙의 실제 원문 호환성도 미확인이다. 기존 0193 classifier는
계속 DIAGNOSTIC_ONLY이며 과거 체크포인트와 원본 SHA를 수정하지 않았다.

Python 3.11의 다음 오프라인 묶음은 **92 passed**: `OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_phase3_obelix_solo_oxide_jats_three_doi_0187.py
tests/test_phase3_obelix_solo_oxide_five_doi_0188.py tests/test_phase3_obelix_solo_oxide_process_transfer_0191.py
tests/test_phase3_obelix_solo_oxide_new_source_0192.py tests/test_phase3_obelix_solo_oxide_nonmonotonic_choice_0193.py
tests/test_phase3_obelix_solo_oxide_author_te_hotpress_0194.py tests/test_phase3_original_cross_paper_transfer_0169.py
tests/test_phase3_original_bulk_grain_routes_0170.py tests/test_development_continuity.py`. 합성 fixture 및
오프라인 regression이며 원문 bytes나 현재 원격 CI를 검증하지 않았다. `check-pr --base-ref worker/k202
--pr-number 375`, `git diff --check` 및 승인 policy digest도 통과했다.

## 서로 다른 CI 원문 경로

`independent-primary-science`(0169)는 Yubuchi DOI `10.1039/c9ra00949c`의
Europe PMC `https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9064144/fullTextXML`
또는 NCBI efetch와 Yu DOI `10.1039/c9ta02126d`의 TU Delft accepted manuscript
`https://pure.tudelft.nl/ws/portalfiles/portal/53254729/C9TA02126D.pdf`를 사용한다.
Yubuchi 수집은 지정 URL별 최대 2회, Yu 수집은 단일 bounded 요청이다.
`actual-original-bulk-grain`(0170)은 다른 Yu DOI `10.1039/c7ta05031c`의
`https://repository.tudelft.nl/file/File_9dd14ba3-3c77-4f77-8383-0918de3062a6`
PDF를 단일 bounded 요청한다. 각 코드는 수신 bytes의 SHA256을 산출하며 해당 경로에
사전 고정된 전체 PDF SHA 비교는 없다. 각기 원문 내용/DOI·크기·페이지 검사를 별도로 수행한다.
현재 CI 로그에 API 접근이 거부됐으므로 어느 URL·계층에서 실패했는지 독립 확인하지 못했다.
사용자 제공 과거 timeout 관찰을 현재 실제 원인으로 단정하지 않는다. 확인된 동등 대체 원문은 없고,
검증을 제거하거나 재시도를 추가하지 않았다.

원문 접근이 가능해지면 각 publisher와 archive에서 정확한 URL·최종 URL·TLS·상태·시간·
representation별 SHA를 기록하고, DOI/PMC 식별 후 해당 표와 문장을 대조한다. 자료가 실제
측정인지 저자 보고 target인지, 총전도도와 bulk 열, 표의 처리 온도와 측정 온도를 별도로 확인한다.
이후에도 독립 모델/과학 자격과 main 병합은 별도 gate다.

## 구조적 문맥 검사 — 후속 개발

`scripts/science/source_context_0193.py:inspect_jats`는 제공된 JATS에 대해 기존 DOI/PMC 및
표·열·행 검사에 더해 측정 Celsius 문맥, S/cm 단위, 시료별 소결 온도·시간 및 총전도도 값을
연결한다. 2018에서 25°C와 298 K가 같은 측정 문단에 있을 때 두 표현을 함께 기록하되
정확히 동일한 수치로 변환하지 않는다. 2020은 표 2의 명시적 25°C와 총전도도 열을 사용한다.
둘 다 유지시간 차이와 공개된 결과의 사후 분석이라는 제약을 포함한다. 허위 DOI, 문단에 없는 25,
열·단위·시료 변경 등의 합성 변조 테스트를 수행했다. 입력 바이트의 로컬 SHA는 반환하지만,
전달받은 문서의 출처는 인증하지 않으므로 항상 `DIAGNOSTIC_ONLY`, `admitted=false`,
`source_authentication=NOT_PERFORMED`, 과학 verdict INCONCLUSIVE다. 논문 원문은 아직 확보되지
않아 이 검사기의 실제 JATS 표현 호환성은 미검증이며, 원문 접근 후 별도의 인증 경로와 문맥 검토가 필요하다.

| 출처 | 측정온도 및 현재 근거 상태 |
|---|---|
| 2018 RSC `10.1039/c8ra01329b` | 25°C/298 K 연결은 사용자 단서와 역사 기록이며 원문 바이트 미확보 |
| 2020 Materials `10.3390/ma13030560` | Table 2의 25°C target은 역사 기록이며 원문 바이트 미확보 |
| 2022 ACS `10.1021/acsomega.2c06544` | 0192 기록상 명목상 실온, 엄격 exact-25°C에서 제외; 이번 원문 미확보 |
| 2023 ChemSusChem `10.1002/cssc.202300399` | 기존 VOR 영수증 바이트 해시만 확인; PDF 재인증 및 25°C 직접 측정 여부 미확립 |

후속 source 관련 묶음은 Python 3.11 / `-p no:cacheprovider`로 **106 passed**: `tests/test_source_context_0193.py`,
기존 0187/0188/0191/0192/0193/0194 테스트, 0169/0170 offline 테스트 및 continuity 테스트.
이후 2022 명목상 실온에 대한 명시적 거부 테스트를 추가한 새 검사기 집중 실행은 **15 passed**다.
최초 합성 2018 fixture는 1200분을 지원하지 않는 기존 공정 parser에 잘못된 숫자 형식으로 표기해
1 failed / 104 passed였고, 동일 시간을 20시간으로 정확히 표현한 후 통과했다. 0202 수동 v2,
0203 자동화·과학검증 및 core MCP 관련 별도 묶음은 **89 passed, 1 warning**이었다.

## 2026-10-28 후속 네트워크 probe 및 기록상의 전체 시료

실행 중인 network policy는 여전히 restricted/enforced이고 원문 host가 허용 목록에 없다.
`curl --max-time 10` read-only 요청에서 `www.ebi.ac.uk`, `eutils.ncbi.nlm.nih.gov`,
`pmc.ncbi.nlm.nih.gov`, `pubs.rsc.org`, `www.mdpi.com`, `api.github.com`,
`pure.tudelft.nl`, `repository.tudelft.nl`, `resolver.tudelft.nl` 모두 **proxy CONNECT 403,
curl exit 56, origin HTTP 코드 000**이었다. 2018/2020 JATS, PMC 및 MDPI XML도 같은
결과였다. 실제 서버 응답이나 논문 bytes는 없으며 각 원문 크기·현재 SHA는 미확인이다.
이전 draft 저장은 실행 환경에 반영되지 않았고 publish 여부도 이 관측만으로 추론하지 않는다.

아래 10행은 `process_feature_identifiability_20261021_v1.json`의 **과거 추출값**이다.
독립적으로 수집된 원문 표가 아니며 총전도도의 직접 측정·등가회로 fitting과 문맥은
원문 확보 후 검토한다. 출처가 서로 다른 표현의 해시를 동일하게 취급하지 않는다.

| 문헌·시료 | 소결 °C | 유지 분 | 역사적 총전도도 S/cm |
|---|---:|---:|---:|
| 2018 LLZALO-1 | 1100 | 1200 | 8.78e-5 |
| 2018 LLZALO-2 | 1150 | 1200 | 1.54e-5 |
| 2018 LLZALO-3 | 1200 | 1200 | 2.80e-5 |
| 2018 LLZALO-4 | 1210 | 900 | 2.10e-4 |
| 2018 LLZALO-5 | 1220 | 600 | 1.32e-4 |
| 2020 SL1 | 1200 | 60 | 1.58e-4 |
| 2020 SL2 | 1200 | 30 | 5.09e-4 |
| 2020 SL3 | 1150 | 60 | 3.49e-4 |
| 2020 SL4 | 1100 | 60 | 5.10e-5 |
| 2020 SL5 | 1100 | 360 | 3.50e-5 |

LLZALO-4/5는 온도·시간이 동시에 달라 `TEMPERATURE_CONFOUNDED_WITH_DWELL`이고,
SL1/SL2는 `SAME_TEMPERATURE_DWELL_TIME_SPLIT`이다. 이 분류는 기존에 기록된 조건의
논리적 관계이며 원문 재인증이나 인과 효과의 증거가 아니다. 사용자 제공 원문 단서에 따르면
2018 본문의 Table 3 25°C 문장과 총/bulk 열의 298 K가 연관될 수 있다. 이를 **합성**
fixture에서만 시험하도록 문맥 추출기를 확장했다. 298 K 열 양쪽과 Table 3 연결이 모순되면
거부한다. `LLZAO-4`라는 본문 단서는 표의 `LLZALO-4` 행 이름을 바꾸지 않는다. 이 두 단서,
직접 등온 EIS 및 등가회로 fitting 해석은 새 바이트로 검증되지 않았다.

0169는 `pure.tudelft.nl/.../C9TA02126D.pdf`의 accepted manuscript 및 별도 PMC JATS,
0170은 `repository.tudelft.nl/file/File_9dd14ba3-3c77-4f77-8383-0918de3062a6` PDF를
요구한다. 현재 proxy가 두 host를 차단해 origin 접근·대체 URL·동일 bytes를 시험하지 못했다.
사용자가 제시한 Islandora 이전 사유는 독립 확인되지 않았고, 현재 코드의 두 URL 자체를
legacy Islandora 경로로 단정하지 않는다. 실제 CI 로그도 API 차단으로 확인되지 않았다.

후속 canonical_table_binding_sha256은 추출한 DOI/시료/공정/측정온도/total 값과 미추출
bulk/Ea/density의 null placeholder를 정규화한 content fingerprint다. 형식이 바뀐 XML의
동일 추출값을 비교할 수 있으나 출처 인증을 증명하지 않는다. 원문을 얻지 못했으므로
full_table_binding_complete=false와 DIAGNOSTIC_ONLY를 유지한다. 제공된 수치만으로 전체
원문 검증이나 등가회로 방법론 인증이 완료됐다고 기록하지 않았다.
