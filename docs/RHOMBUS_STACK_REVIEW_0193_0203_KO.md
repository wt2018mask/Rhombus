# 0193–0203 순차 통합 검토

검토일 2026-10-28. 판정: **REVIEW_BLOCKED**. 소프트웨어 통합 검토이며 과학적 독립 검증이나 병합 승인이 아니다. 운영 준비는 NO_GO다.

## 0193 / PR #363

- Git 원격 조회: main `1aaaa555a9a1ce2c9123845402fec4e664626708`, 363 HEAD `3c2f42f6f5c3c88acfb55fcd6cdf7acab8b76802`. merge-base는 main이고 5개 커밋, 8개 변경 파일이다. 최신 PR 상태 및 정확한 HEAD의 CI는 이 환경에서 GitHub API가 Forbidden을 반환해 재검증하지 못했다. `docs/SOURCE_RECOVERY.md`의 56/56은 과거 관찰이다.
- 전체 diff: README, CURRENT, 0193 이벤트, 생성 handoff, 과학 문서 두 개, 스크립트 및 전용 테스트를 검토했다. 0192에서 0193으로 이벤트 하나가 추가되고 다음 동작은 0194다. 기록된 NO-GO, production OFF, 물리 P0 0/3 BLOCKED는 유지된다. 변경 파일에 신규 비밀값이 보인다는 증거는 없으나 간단한 텍스트 검토는 전체 이력 보안 감사가 아니다.
- 일회용 복제본에서 정확한 main에서 HEAD로 fast-forward 성공, `continuity.py check`, `check-pr --base-ref 1aaaa555a9a1ce2c9123845402fec4e664626708 --pr-number 363`, `git diff --check` 통과. 처음 `origin/main`을 사용한 check-pr은 로컬 복제본에 그 이름의 ref가 없어 실패했으며, 동일한 정확한 SHA로 재실행해 통과했다. 원본 main은 변경하지 않았다.
- 전용 0193 및 continuity 테스트 7개, 기존 0191/0192 테스트 9개 통과. 원문 재다운로드, 독립 과학적 수용, canonical Wave 2의 현재 원격 결과는 검증하지 않았다.

### 재현된 첫 통합 게이트

0193 `classify`는 `exact_25C`가 bool인지 검사할 뿐 원문이나 출처를 인증하지 않는다. `SOURCES[0]`에 가짜 DOI와 임의 best sample, `exact_25C=True`를 주면 `admitted=True`를 반환한다. 고정된 내장 입력에 대한 소급 진단으로는 동작하지만, 문서의 일반적인 ‘source admissibility gate’ 또는 임의 입력의 인증 기능으로 해석하면 부정확하다. `report([])`도 0191/0192 역사적 성공·실패 플래그를 True로 반환한다. 이는 해당 입력에서 계산된 결과가 아니라 고정된 과거 주장이다. 결과는 항상 INCONCLUSIVE이고 GO 및 production은 false이므로 재현한 경우 자동 과학 승격은 없었다.

선행 0188의 2018 원문 검증은 문서 전체에 문자열 `25`가 있는지 확인하며, 0187의 2020 표 캡션 검사도 `25`만 포함해도 통과한다. 따라서 그 검사 자체는 해당 측정의 정확한 25°C 문맥을 증명하지 못한다. 이것은 실제 원문이 틀렸다는 발견이 아니다. 0191 문서는 원문 JATS와 과거 실행 38899828332 및 결과 ZIP SHA256을 기록하고, 코드가 표의 시료와 공정·전도도 값을 대조한다. 그러나 이번 검토에서 원문 바이트와 해당 실행 산출물을 독립적으로 확보·재검증하지 못했다. 0193의 숫자와 기존 exact-25°C 주장은 기록된 선행 증거에 의존하며 독립 검증은 미완이다.

내장 자료에 한정하면 2018의 1210°C 최고와 1220°C 선택 실패, 2020의 1200°C 동률에 대한 기권, 2022의 정확한 온도 미상 배제는 테스트와 일치한다. 서로 다른 공정에는 유지시간도 달라 순수 온도 인과 효과를 증명하지 않는다. 2018은 이미 노출된 음성 대조군이며 새로운 독립 검증이 아니다. 따라서 데이터 원문과 숫자의 별도 검증 없이 이를 과학적 선택 성공으로 승격할 수 없다.

병합 검토를 진행하려면 (1) 실제 원문과 원문-측정온도-시료-수치 연결을 검증 가능한 출처 및 해시와 함께 확인하고, (2) 입력 인증과 고정 역사 진단의 경계를 명확히 하고 적대적 테스트로 잘못된 인증 또는 고정 플래그의 오용을 막거나 명시적으로 제한하며, (3) 수정의 다운스트림 정체성 영향을 검토하고 최종 HEAD의 필수 CI와 연속성을 확인해야 한다. 과거 체크포인트 및 동결된 증거를 덮어쓰지 않는다.

## 0194 / PR #364: 예비 검토만

원격 Git HEAD `03c1bd5b1ba37284d73577c8fd58e4382b0d4251`은 363 HEAD의 후손이고 이벤트 0194는 `parent_stack_pr: 363`을 명시한다. 이전 사건의 미해결 출처 인증 경계가 첫 선행 게이트다. 0194의 `SOURCE_RECOVERY.md`는 별도의 기관 VOR 원문에 대한 과거 인증 영수증과 18개 셀 연결을 기록하지만, 최근 접근 불가와 역사적 영수증 연속성은 현재 원문 인증과 구별한다. 18개 조건은 한 논문이며 25°C 표 값이 정확히 그 온도에서 직접 측정되었다는 증명은 아니다. HOT_PRESS 56 MPa는 기존 0191 모델 범위 밖으로 기권한다. 0194 전체 감사와 최신 CI 확인은 아직 하지 않았다.

## 남은 순서

0193 게이트 해소 및 exact-head CI 확인 후에만 0194 전체 검토, 이후 0195 → 0196 → 0197 → 0198 → 0199 → 0200 → 0201 → 0202 → 0203 순서로 각 상위 의존성 및 독립 증거를 검토한다. 0194는 예비 검토, 0195–0203은 이번 순차 통합 감사에서 **UNREVIEWED**다. 이 문서는 병합, 생산 설정 변경 또는 Kaggle 실행을 승인하지 않는다.

## 2026-10-28 후속 증거 및 0194 검토

아래 상태는 2026-10-28 UTC의 관찰이다. URL의 원문은 이번 환경의 강제 네트워크 허용 목록에 없어 직접 수집하지 않았다. GitHub API는 Forbidden이므로 과거 Actions 산출물의 보존·접근 여부와 최신 CI를 조회하지 못했다. 원문 또는 과거 실행을 새로 인증했다고 주장하지 않는다. SHA가 없는 항목은 이번에 원문 바이트를 얻지 못했다.

| 주장 / 식별자 | 원문·위치 및 조건 | 측정 온도 및 확인 경로 | 상태 / 한계와 다음 조치 |
|---|---|---|---|
| 0193-RSC, DOI 10.1039/c8ra01329b | https://doi.org/10.1039/c8ra01329b ; PMC9079727 JATS 표 1/3, LLZALO-4 1210°C vs LLZALO-5 1220°C, 유지 시간도 다름 | 0191 보고는 25°C TOTAL을 주장. `obelix_solo_oxide_five_doi_0188.py:original_2018`의 전체 텍스트 `25` 검사는 측정 문맥을 증명하지 못함 | INDEPENDENT_REVALIDATION_PENDING; 원문 SHA 미확보. 원문 정확한 문맥과 표의 값·시료 연결 재확인 |
| 0193-Materials, DOI 10.3390/ma13030560 | https://doi.org/10.3390/ma13030560 ; PMC7040616 JATS 표 2, SL1/SL2 1200°C 동률 | 0191 보고는 25°C TOTAL을 주장. `obelix_solo_oxide_jats_three_doi_0187.py:parse_article` 캡션의 `25`만으로 충분하지 않음 | INDEPENDENT_REVALIDATION_PENDING; 원문 SHA 미확보. 실제 표 캡션·열과 조건을 독립 재확인 |
| 0193-ACS, DOI 10.1021/acsomega.2c06544 | https://doi.org/10.1021/acsomega.2c06544 ; 0192 JATS 조건별 1050/1100°C, 6시간 | `obelix_solo_oxide_new_source_0192.py`는 RT를 exact 25°C에서 제외. 이번에 원문 미확보 | SOURCE_UNAVAILABLE; 역사적 RT 주장만 확인, 정확한 온도·표 연결 재확인 |
| 0194-VOR, DOI 10.1002/cssc.202300399 | https://iris.unimore.it/handle/11380/1328508 ; 기관 VOR 표 2, Te0.1 650°C 1.76e-5 및 700°C 1.45e-5 S/cm, 56 MPa | 표의 저자 보고 25°C 목표; 각 값이 그 온도에서 직접 측정됐는지는 미입증. `verify_unimore_vor_0194.py`의 과거 영수증에 18개 셀 및 원문 PDF SHA256 `871e6ff252cce27799e8e2bf5455667bdaf6dc639dde2875ad57a4ecce5fc58b` 기록 | HISTORICAL_RECEIPT_VERIFIED: 저장소 영수증 SHA256 `4cce0d4b9329e369d61db5116687c7297316fbda77be63fb96f1cbac6de18b75`가 코드에 고정된 값과 일치. 이는 PDF 바이트 재검증이나 과거 실행의 독립 인증이 아님. INDEPENDENT_REVALIDATION_PENDING |

0191/0192 워크플로는 고정 OBELiX Git 커밋과 Europe PMC JATS를 사용하고 산출물 보존기간은 30일이다. `get_jats`는 최종 URL을 검사하지만 기본 URL opener의 사전 리디렉션 제한은 아니다. JATS 해시가 선행 산출물에 기록되도록 되어 있으나 이번에는 해당 산출물 접근 불가다. 0194는 Wiley HTML 가용성, 명시적 동결표 진단, 기관 VOR 과거 영수증/현재 가용성을 별도 작업으로 구분한다. 기관 경로는 HTTPS 호스트와 PDF SHA를 고정하고 문헌 식별, 권리, 표 셀·문자 글리프를 검사한다. 현재 접근 불가 시 과거 영수증 연속성만 보고한다. 경로 필터가 6개 기존 원문 워크플로의 PR 실행 범위를 좁힌 점도 확인했으며, 필터로 실행되지 않은 체크를 통과로 간주할 수 없다. OSTI 문서 수집은 허용 호스트·최종 URL, 크기·SHA, 제한된 429 재시도를 검사한다.

### 전방 수정 및 잔여 통합 판정

0193은 접근 방식 A를 선택했다. v2 출력에서 `admitted`는 항상 false, `diagnostic_eligible`은 오직 입력 주장에 대한 계산이며 원문 인증은 `NOT_PERFORMED`다. 동적 건수도 진단으로 명명하고 고정 0191/0192 플래그는 역사적 기록이며 입력에서 재계산되지 않았다고 명시했다. 저장소 검색에서 이 스크립트를 독립 출처 인증에 사용하는 다른 호출자는 발견하지 못했다. 이전 Git 기록은 변경하지 않았고 출처 원문 인증 API를 임의 해시로 만들지 않았다.

0194 코드의 추가 결함: 구 버전은 `original_html`로 파싱한 임의의 로컬 HTML/합성 fixture를 `evaluate`에서 기본적으로 live verified로 표시했다. 전방 수정은 분석 결과를 항상 DIAGNOSTIC_ONLY로 표시하며 로컬 해시가 원문 출처를 입증하지 않는다고 명시한다. Wiley 별도 실시간 probe는 출판사 HTTPS 호스트 제한 리디렉션과 최종 URL 확인을 추가한다. 소급 진단 및 접근 불가가 분리된다. 고정된 0193/0194 PR HEAD에는 이 수정이 포함되지 않으므로 두 PR의 원래 통합 판정은 **REVIEW_BLOCKED**다. 변경분을 선행/후속 통합 시점에 어떻게 적용할지 검토하고 실제 원문 및 최종 CI를 확인해야 한다.

0194의 21개 변경 파일 전체 범위를 확인했다. 하나의 논문과 여섯 명목 조성의 18조건이지 18개의 독립 논문이나 확인된 독립 시편이 아니다. 0191 모델은 해당 600–700°C, 56 MPa hot press에 대해 6/6 기권한다. 선택 우월성, 통계적 유의성, 직접 25°C 측정 및 과학 GO는 증명하지 못한다. README의 간략한 출처 표현은 `SOURCE_RECOVERY.md`의 현재/과거 구분과 함께 읽어야 한다. 0194 전체 소프트웨어 검토에도 불구하고 위 원본 HEAD 결함, 0193 선행 게이트 및 실시간 출처·CI 미확인 때문에 REVIEW_BLOCKED다. 0195–0203은 이번 순차 통합 감사에서 UNREVIEWED다.

일회용 복제본에서 PR 363 HEAD를 기준으로 PR 364 HEAD를 fast-forward했고 `continuity.py check`, `check-pr --base-ref 3c2f42f6f5c3c88acfb55fcd6cdf7acab8b76802 --pr-number 364`, `git diff --check` 통과. 원래 0194 HEAD에서 0194/원문 검증/0153/0193/연속성 테스트 75개 통과. 전방 수정 테스트 결과는 커밋 및 PR 검증 보고에서 별도 기록한다. 실제 외부 원문 수집과 Kaggle 작업은 수행하지 않았다.

전방 수정은 Python 3.11.17 / pytest 9.1.1에서 다음 명령으로 **96 passed**, 원격 원문 테스트 없음: `.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_phase3_obelix_solo_oxide_nonmonotonic_choice_0193.py tests/test_phase3_obelix_solo_oxide_author_te_hotpress_0194.py tests/test_verify_unimore_vor_0194.py tests/test_phase3_public_manuscript_0153.py tests/test_phase3_obelix_solo_oxide_process_transfer_0191.py tests/test_phase3_obelix_solo_oxide_new_source_0192.py tests/test_development_continuity.py`. `check-pr --base-ref worker/k202 --pr-number 375`와 `git diff --check` 통과. 0193 입력 변조 및 0194 로컬 HTML·외부 리디렉션을 포함한다. 이 테스트는 보안 전체 감사가 아니다.

## 전방 수정의 통합 배치 — 2026-10-28

**권고: C의 원자적 통합 후보를 조건부로 준비하되 현재는 통합하지 않는다.** 정확한 main `1aaaa555a9a1ce2c9123845402fec4e664626708` → 0193 HEAD `3c2f42f6f5c3c88acfb55fcd6cdf7acab8b76802` → 0194 HEAD `03c1bd5b1ba37284d73577c8fd58e4382b0d4251` → 원래 0195–0203 스택 및 0202 source `474df8faa7484b87f19e5679336192939598e1f7` → `2ce8386998f3008c694579c1b6a918ff731b44d8`의 전방 보완 → 이 문서와 후속 진단 경계 수정 순서로 Git 선조관계를 보존한다. 개발용 복제본에서 192 main에서 2ce8386까지 fast-forward했고 중간의 0193/0194와 동결 source가 선조임을 확인했다. 중간 상태는 배포·과학 사용 금지다. 원자성은 전체 수정 포함 최종 트리를 단일 검토 대상 PR로 main에 반영하는 조건이지 이 리허설의 승인이 아니다.

| 원래 소유 | 전방 수정과 파일 | 배치 및 조건 |
|---|---|---|
| 0193 #363 | 2ce8386 `scripts/science/obelix_solo_oxide_nonmonotonic_choice_0193.py`, 전용 테스트; 이후 진단 출력 표기 수정 | 기존 사건 뒤에 위치; 허위 DOI·온도·시료 입력은 인증 불가. 원문 온도 문맥 재검증 및 0191–0193 테스트 필요 |
| 0194 #364 | 2ce8386 `scripts/science/obelix_solo_oxide_author_te_hotpress_0194.py`, 전용 테스트 및 0194 workflow; 이후 카운트·URL·단위 수정 | 기존 사건 뒤에 위치; 출판사 probe, 로컬 진단 및 과거 VOR 영수증 분리. 실제 VOR 재수집, 0194 source/테스트 및 정확한 HEAD CI 필요 |
| 0200–0203 | 변경하지 않은 동결 프로토콜·소스 및 자동화 정책 | `474df8...`는 선조로 보존하고 source를 재바인딩하지 않음. 0201 프로토콜 및 정책 해시, 원본 inventory 확인. 생산은 NO_GO |

전략 A의 개별 순차 병합은 수정 전 진단이 main에서 사용될 기간을 만든다. 운영 OFF만으로 다른 소비자의 사용을 막는 증거가 없으므로 안전한 배포 경로로 승인하지 않는다. 전략 B의 역사 브랜치에 새 커밋을 덧붙이면 과거 커밋은 보존되지만 364 이하의 기존 선조는 새 363 HEAD를 포함하지 않는다. 이후 각 브랜치의 병합 기반, 정확한 HEAD CI·리뷰 및 다운스트림 source/해시를 재검토해야 하므로 현재 실행하지 않는다. 전략 C는 기존 모든 커밋을 보존해 수정 없는 중간 main 상태를 피하지만 큰 범위의 종속 스택 전체 리뷰와 CI가 필요하다.

리허설의 `continuity.py check`는 통과했고 main 기준 `check-pr`은 정상적으로 거부됐다: 일반 PR은 이벤트 하나만 허용하지만 후보는 0193–0203 11개를 추가한다. 따라서 이 스냅샷은 **독립적으로 유효한 현재 통합 PR이 아니다**. 예외 `STACK_REPAIR`는 이미 검증된 연속 범위에만 사용하며 정확한 main SHA, base index 192, range [193,203], 해당 통합 PR 번호 및 생성 handoff를 일치시켜 별도 검토해야 한다. 지금 0193/0194는 REVIEW_BLOCKED, 0195–0203 순차 감사는 미완이므로 조건이 충족되지 않는다. 규칙을 우회하거나 가짜 이벤트를 추가하지 않았다. 필요한 소유자 결정은 모든 선행 게이트가 해소된 뒤 이 원자적 후보의 별도 통합 검토를 승인할지 여부다. 병합은 별도 승인이다.

잔여 신호 감사: 0194 진단의 `author_original_DOI_count`, `new_original_DOI_evidence`, `new_independent_papers`는 과거에 각각 1이어서 인증 건수처럼 해석될 위험이 있었다. 진단 v2는 세 값을 0으로 두고 별도의 `diagnostic_reported_DOI_count=1`로 표시한다. 로컬 입력 해시는 `diagnostic_input_html_sha256`이며 `first_party_html_sha256`은 null이다. Wiley 경로는 고정 DOI 경로·HTTPS 호스트·포트·최종 URL과 표의 S/cm 단위를 검사한다. 출판사 probe의 성공조차 과학 GO가 아니다. 원문 측정 맥락과 셀 해석은 추가 독립 검증이 필요하다. 진단을 sealed 평가 프로토콜로 제출하면 스키마 검사에서 거부되는 테스트를 추가했다.

코드·workflow 검색상 0193/0194 진단 카운트를 자격 판정에 전달하는 소비자는 발견하지 못했다. 0198 `load_study`는 진단 출력이 아니라 정확한 해시로 고정된 과거 VOR 영수증만 사용하며, 0195 MCP replay도 해당 영수증 해시를 확인한다. 이것은 원문 바이트의 현재 독립 인증이 아니다. 감사는 저장소 내 정적 검색과 지정된 소비자 테스트 범위에 한정된다. 2018·2020·2022 원문 및 2023 PDF는 현재 허용된 네트워크 경로에서 얻지 못했고 새 SHA 또는 과학 결론은 없다. GitHub API Forbidden으로 현재 CI 및 원격 산출물 상태는 재확인할 수 없다.
