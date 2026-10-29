# 0203 배포 의존성 및 원장 초기화 검토안

이 문서는 배포 요청이 아니다. 2026-10-27 현재 production 및 Kaggle preflight는 NO-GO다.
자동 실행, 비밀정보, 환경 규칙, 운영 원장은 수정하지 않았다. 원본 출처 실패는
과학 검증을 대체하지 않는다. 0203 PR #375는 worker/k202를 기반으로 한다.

## 재현 가능한 파일별 목록

`python -m scripts.tools.kaggle_deployment_inventory > inventory.json`은 현재 checkout의
컨트롤러 파일 목록과 고정 science commit의 **283개 파일 각각의 경로와 SHA256**, 0200
부모 report SHA256 및 **20개 결과 파일 각각의 경로와 SHA256**을 출력한다. 실제 Git
커밋 바이트를 전부 다시 읽어 확인하며 공개 키·토큰·네트워크 요청을 사용하지 않는다.
현재 science commit `474df8faa7484b87f19e5679336192939598e1f7`은 로컬에서 검증됐으나
main `1aaaa555a9a1ce2c9123845402fec4e664626708`의 조상이 아니다. 다른 브랜치의
커밋이 앞으로 GitHub에서 계속 fetch될 것이라는 보장은 없다. 실제 Actions와 Kaggle
환경에서 정확한 SHA checkout 접근성 및 장기 보존은 UNVERIFIED다.

| 단계 | 필요한 구성요소 |
| --- | --- |
| 공통·preflight | `rhombus/automation/{__init__,cli,controller,kaggle,ledger}.py`, `policy.json`, `request.json`, `.github/workflows/kaggle-thermal-controller.yml`, Python 3.11, kaggle 2.2.5, kagglesdk 0.1.38, requests, main 전용 `kaggle-production`, `KAGGLE_API_TOKEN`, `KAGGLE_USERNAME` 변수/secret 또는 계정 기본값, `RHOMBUS_POLICY_SHA256` |
| 최초 제출 | 위 구성요소와 `worker.py`, 승인된 `RHOMBUS_LEDGER_ROOT_SHA`, 독립적으로 검증된 원장 보호·단일 작성자·bypass 제한, 정확한 science commit 및 283개 소스, 인터넷, CPU 전용 torch/MACE와 검증된 공개 모델 바이트 |
| 상태 재조회·복구 | `controller.py`, `kaggle.py`, `ledger.py`, 공급자 인증, 보호된 원장과 루트 SHA, 원격 작업 식별자. 불확실한 제출은 재시도하지 않음 |
| 과학 검증 | `verify.py`, 고정 science checkout, 고정 report 및 20개 자료, numpy/scipy/ASE/pymatgen/smact/pyyaml 및 checkout의 constraints. torch/MACE 재실행 없음 |
| 증거 게시 | `archive.py`, 검증 결과·raw 파일, GitHub release 작성/읽기·asset 다운로드 및 원장 CAS 권한. release 보존과 재읽기 필요 |
| 선택 개발 도구 | `mcp_server.py`, 기존 `rhombus/tools` 및 MCP SDK, `.github/workflows/kaggle-automation-tests.yml`, 테스트, readiness/inventory/bootstrap 검사기 |

Python import와 Git 파일 목록은 검토 범위이며, 이 목록만으로 독립된 main checkout의
실제 실행이 입증된 것은 아니다. 공통 `rhombus/__init__.py`와 관련 `rhombus/tools` 등
transitive import도 필요할 수 있다. `scripts/science/thermal_study_0201.py`,
`rhombus/atomistics/thermal_study.py`, `rhombus/evidence/`와 0200 자료는 고정 checkout에서
사용한다. inventory는 정확한 바이트 목록을 제공하고, 최소 설치 범위의 독립 smoke test는
아직 수행되지 않았다. 일반 PR에는 main 다음 checkpoint 하나와 CURRENT/HANDOFF 갱신이
필요하다. main이 0192이고 이 스택은 0203이므로, 0203만 선택 적용해 순차 이력을 주장하는
별도 PR은 만들지 않았다. 합법적인 연속성 결정과 고정 checkout의 외부 접근 검증 후
별도 review가 필요하다.

## 한 번만 수행하는 소유자 절차

| 순서 | 동작과 권한 | 변경 | 성공 증거 / 차단 조건 |
| --- | --- | --- | --- |
| 1 | 관리자·독립 감사자가 `kaggle-production`을 main 전용으로 제한하고 규칙셋/우회자·유효 보호·단일 작성자를 검토 | 예 | 유효 규칙과 허용 작성자 확인. 403, 미확인 bypass 또는 불필요한 작성자면 중단 |
| 2 | 소유자가 아래 바이트로 로컬 parentless root 준비, 별도 감사자가 SHA와 구조를 확인 | 로컬 Git 객체만 | 오프라인 검사는 구조만 확인. 소유자 승인·운영 브랜치 연결·실효 보호는 별도 증거 |
| 3 | 소유자가 생성 전 적용되는 보호가 유효함을 확인한 뒤 operational ref를 최초 한 번 생성 | 예 | 정확한 ref/root 및 규칙을 재조회. 실패·응답 유실 시 조회하여 조사, 맹목적으로 재생성 금지 |
| 4 | 소유자가 검증한 root SHA와 승인된 정책 SHA를 환경 변수에 기록하고 기존 `KAGGLE_API_TOKEN`을 재사용할 수 있는지 관리 화면에서 확인 | 예 | `RHOMBUS_LEDGER_ROOT_SHA`, `RHOMBUS_POLICY_SHA256=921f430a7e2435c763760f9ac866306c15ac7dc14572353ca76b4a2d682a1ea2`; 비밀값은 노출하지 않음 |
| 5 | 독립 감사자(관리 설정 읽기), 런타임(필요한 contents/actions), 소유자(한 번만 설정)의 권한을 분리 | 필요 시 | 보호 API, environment 정책, bypass 및 작성자를 각 실제 identity로 읽을 수 있어야 함. 현 통합 identity의 403은 UNVERIFIED |
| 6 | 별도 승인된 배포 및 main 통합 후 소유자가 읽기 전용 preflight를 명시적으로 승인 | 예, 배포 | 기존 토큰으로 실제 계정 확인 성공 전까지 인증·무료 quota는 UNVERIFIED. preflight는 작업 생성하지 않음 |
| 7 | 별도 승인 전에는 자동화 변수 활성화와 Kaggle 제출을 금지 | 아니오 | 활성화·과학 계산은 별도 결정. policy lifetime 최대1회, 재시도0회 |

GitHub의 해당 API에 필요한 최소 권한과 workflow `GITHUB_TOKEN`의 실제 접근 가능성은
이 환경의 403 때문에 **검증되지 않았다**. GitHub App의 별도 관리 읽기 권한은 후보일 뿐
발급이나 적용을 권고된 설정으로 단정하지 않는다. 이 통합 계정이나 토큰을 untrusted PR
코드 또는 Kaggle worker에 주입하지 않는다. 정확한 권한은 소유자의 실제 플랜·설정과
공식 API 문서 및 해당 identity의 읽기 전용 관측으로 확정한다.

## 최초 루트의 정확한 내용

`state.json`은 UTF-8 다음 바이트 뒤에 LF 하나를 붙인 파일이다:

```json
{"schema_version":"rhombus-automation-ledger-bootstrap-v1","state":"UNCLAIMED"}
```

Git tree는 **오직** `100644 blob <state.json-blob>\tstate.json` 하나를 포함하고, commit은
부모가 없어야 한다. author/committer/time에 따라 commit SHA는 달라지므로 가짜 운영 SHA를
미리 하드코딩하지 않는다. 로컬의 준비된 루트를 아래 read-only 검사로 검토한다:

```bash
python -m scripts.tools.validate_kaggle_bootstrap --repo /path/to/local/git/repo --root-sha <full-reviewed-sha>
```

구조 PASS는 승인, 운영 ref 바인딩, 실제 보호 또는 제출 권한이 아니다. 승인된 루트 SHA는
`RHOMBUS_LEDGER_ROOT_SHA`에서 독립적으로 공급되며 runtime은 ref 생성이 불가능하다.
이력 교체·삭제·recreation·다른 쓰기 주체·관리자 bypass가 가능하면 SHA만으로 lifetime
제출 횟수를 보장하지 못한다. 루트 준비/생성 중 응답이 유실되면 원격 ref와 모든 규칙을
독립적으로 재조회하고 모호한 상태를 보존한다. 보호된 root 이외의 상태로 첫 CAS를
실행하지 않는다. 정확히 한 번 원격 실행을 주장하지 않는다.

추가 read-only 관측: 2026-10-27 GitHub Git commit API가 위 science SHA를 반환했고,
원격 `worker/k202` ref도 같은 SHA를 가리켰다. 이는 해당 시점의 API 접근 증거이며
Actions/Kaggle의 fetch 성공이나 향후 ref 보존을 보증하지 않는다.
