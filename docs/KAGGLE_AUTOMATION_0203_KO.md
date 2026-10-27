# 0203: 제한된 Kaggle 자동 실행 컨트롤러

이 구현의 운영 수용 상태는 `REMOTE_SCIENCE_NOT_EXECUTED`이다. 실제 Kaggle 인증,
CPU 실행, 출력 회수는 아직 검증되지 않았다. 합성 테스트를 원격 과학으로 등록하지 않는다.
0200 결과와 0201 프로토콜, 0202 수동 복구 Notebook, sAlex 제한은 유지한다.

## 실행 경로

`rhombus.automation.mcp_server`의 추가 도구 `request_approved_thermal_study`는 main의
컨트롤러에 재조회를 요청한다. 임의 Python, 소스, 모델, 자원, 정책 인자는 받지 않는다.
`get_automated_thermal_evidence`는 GitHub 원장과 검증된 EvidenceRecord를 자동으로 읽고
기존 여섯 도구가 사용하는 로컬 읽기 전용 스냅샷을 갱신한다. 기존 MCP 서버는 그대로다.

`kaggle-thermal-controller.yml`은 기본 브랜치에 배포된 뒤 30분 간격으로 재개한다.
GitHub 스케줄 지연/누락은 가능하다. 한 번에 상태를 한 번 조회하고 종료한다.
정책은 전체 수명 동안 정확히 하나의 0201 CPU 작업, 동시성 1, 제출 재시도 0,
10800초, 4096 MiB 관측 RSS, 과학 출력 128 MiB, 지출 $0을 허용한다.
GPU 및 추가 작업군은 허용하지 않는다. 정책 밖 작업은 독립적으로 검토한 새 구현과
정책 없이는 실행할 수 없다. 프로토콜은 원래의 550 K, float64, 두 CPU 스레드다.

공식 `kaggle==2.2.5`, `kagglesdk==0.1.38` 인터페이스를 사용한다.
버전 1의 소스, 상태, 출력 목록을 인증된 API에서 조회한다. SDK의 제출 HTTP 호출에는
재시도 루프가 없음을 확인했으며 컨트롤러도 제출을 재시도하지 않는다.
과학 패키지는 기존 동결 constraints와 런타임 핀을 사용한다. Kaggle에서 실제 설치
성공 여부와 전체 전이 의존성 재현성은 아직 검증되지 않았다.

## 원자적 소비와 복구

`rhombus-automation-ledger-v1` 브랜치의 단일 state.json이 전역 원장이다.
초기 원자적 ref 생성이 제출 권한을 소비한다. 각 청구에는 난수 nonce가 있어 서로 다른
컨트롤러가 동일 커밋을 만드는 문제를 피한다. 후속 커밋은 읽었던 tip 하나만 부모로
갖는다. 경쟁하는 형제 커밋 중 하나만 `force:false` 갱신에 성공할 수 있다.
GitHub 응답 유실은 성공으로 간주하지 않는다. 저장된 SUBMISSION_PENDING 이후의
재개 경로에는 push 호출이 없다. 제출 전 취소는 미소비, 소비 후 취소는 재조회만 한다.

실제 GitHub API 경쟁 시험은 `data/development/automation0203/github-cas-probe.json`에
기록했다. 고유 시험 브랜치는 감사용으로 보존하며 운영 원장을 사용하지 않았다.
이 관측은 현재 API의 at-most-once 자동 제출 구현을 뒷받침한다. 관리자에 의한 원장
삭제/재작성, 별도 수동 Kaggle 실행까지 막는 exactly-once 보장은 아니다.
원장 삭제/force push를 막는 규칙을 초기 배포에 포함해야 한다.

응답이 불확실하면 결정적 `계정/rhombus-0201-작업해시앞40자리/1`을 조회한다.
소스 바이트, 비공개 설정, CPU 설정, 버전이 다르면 실패한다. 없는 작업, 조회 실패,
실행 전 중단을 구분할 수 없는 경우 `SUBMISSION_OUTCOME_UNCERTAIN`을 유지한다.
같은 과학 작업을 다른 ID로 자동 재발급하는 경로는 없다.

## 출력, 검증, 보존

SDK 출력 목록에서 result/ 파일만 선택하고, 허용된 HTTPS 저장소에서 비밀 헤더 없이
한도 내 스트리밍 다운로드한다. 부분 다운로드는 검증되지 않으며 다음 재조회에서
새 임시 디렉터리에 다시 회수한다. 재회수는 과학 계산 재제출이 아니다.
소스 조회와 출력 조회 사이에도 버전/소스를 다시 확인한다.

비밀 없는 별도 단계에서 기존 `verify_thermal_result_artifacts`를 호출한다.
이 검증기는 열역학 통계와 P2 구조 판정을 궤적/원시 trace에서 다시 계산한다.
NPZ의 압축 해제 크기도 제한한다. 빈 결과/변조/실패는 증거 레코드를 만들지 않는다.
부분 과학 결과는 COMPLETE로 승격하지 않는다. 제공자 COMPLETE는 과학적 PASS가 아니다.

원시 파일, 제공자 로그, 검증 보고서, EvidenceRecord를 해시 이름의 GitHub Release
asset에 보관하고 다시 내려받아 SHA256을 확인한 뒤 원장에 결과를 연결한다.
워크플로 아티팩트의 만료를 영구 보존으로 오인하지 않는다. Release도 소유자 삭제와
서비스 정책 변경으로 사라질 수 있다. 자동 삭제와 큰 바이너리 Git 커밋은 없다.
업로드/재다운로드/공개 게시의 실제 제공자 검증은 아직 수행하지 않았다.

인증된 버전 API 관측은 런타임 원격 증명이 아니다. 이 한계가 EvidenceRecord에 남는다.
모델 적용성은 UNQUALIFIED, 과학 판정은 INDETERMINATE, qualification은 ABSTAIN이며
전도도는 null이고 P3는 BLOCKED다. 새 실제 열역학 수치를 주장하지 않는다.

## 최초 한 번의 설정

1. 컨트롤러 배포 PR을 검토한다. 승인 없이 main에 병합하거나 worker 브랜치에
   Kaggle 비밀을 제공하지 않는다. main에 스케줄 워크플로가 있어야 자동 운용이 시작된다.
2. GitHub Settings → Environments → kaggle-production에서 Deployment branches and tags를
   Selected branches and tags로 바꾸고 **branch main만** 허용한다. 일상 작업마다 승인을
   요구하는 reviewer 규칙은 필요하지 않다. 저장소 main과 원장 브랜치에 삭제/force push
   방지 규칙을 설정하고 원장 쓰기는 신뢰된 컨트롤러로 제한한다.
3. 과거 GitHub 저장소 Secret에 `KAGGLE_API_TOKEN`이 남아 있다면 새 컨트롤러가
   그 이름을 그대로 사용한다. 같은 이름의 환경 Secret이 있으면 환경 Secret이 우선한다.
   Secret 존재와 현재 유효성은 과거 실행 기록만으로 단정할 수 없다. 토큰이 없다면
   Kaggle Settings → API → Generate New Token에서 새 토큰을 발급받아
   `kaggle-production` 환경 Secret `KAGGLE_API_TOKEN`으로 직접 저장한다.
   채팅, 파일, Notebook, 명령행 인자에 토큰을 입력하지 않는다.
   `KAGGLE_USERNAME` + `KAGGLE_KEY`만 있는 과거 설정은 토큰 전용 0203과
   아직 호환되지 않으며, 이 변경은 기존 비밀 키를 토큰으로 변환하지 않는다.
4. `KAGGLE_USERNAME`에는 비밀이 아닌 정확한 계정 이름을 사용한다. 우선
   환경/저장소 Variable `KAGGLE_USERNAME`을 사용하고, 값이 없으면 과거
   Secret `KAGGLE_USERNAME`을 재사용한다. 둘 다 없으면 과거 실제 Kaggle
   작업에서 확인된 `wt2018mask` 계정 이름을 기대값으로 사용한다. 인증 토큰에서
   조회한 계정 이름이 기대값과 다르면 실패하므로 다른 계정으로 제출하지 않는다.
   정책을 검토한 뒤 환경 변수 `RHOMBUS_POLICY_SHA256`에 다음 값을 설정한다:
   `921f430a7e2435c763760f9ac866306c15ac7dc14572353ca76b4a2d682a1ea2`.
   `python -m rhombus.automation.cli policy-digest`로 재확인할 수 있다.
5. 활성화 변수는 아직 설정하지 않고 Actions에서
   Trusted Kaggle thermal controller → Run workflow → operation=preflight를 한 번 실행한다.
   성공 기준은 실제 토큰 introspection과 인증된 자기 kernel 목록 조회의 성공이다.
   단순히 secret 이름이 존재하는 것은 연결 성공이 아니다.
6. 인증 시험 성공 후 저장소 변수 `RHOMBUS_AUTOMATION_ENABLED=true`를 설정한다.
   정책 승인은 정확한 한 CPU 작업의 자동 실행을 포함한다. reconcile을
   한 번 요청하거나 다음 스케줄을 기다린다. 이후 수동 Notebook 실행/ZIP 다운로드/
   가져오기/작업별 확인 문구는 없다. 수명 한도 1을 모두 쓰면 추가 작업은 자동 차단된다.

preflight는 활성화 변수 없이 실행할 수 있지만 제출은 하지 않는다. 활성화 변수를
설정하기 전 스케줄과 MCP가 요청한 reconcile은 실행되지 않는다.

MCP 호스트는 `python -m rhombus.automation.mcp_server`로 시작한다.
호스트 `GH_TOKEN`에는 이 저장소의 Contents 읽기와 Actions 쓰기만 부여한다.
Kaggle 토큰은 MCP 호스트에 주지 않는다. MCP 요청은 제공자 권한을 가지지 않는다.

## 확인한 차단 요인

현재 로컬 KAGGLE_API_TOKEN은 없고, kaggle-production 환경의 secret 목록은 비어 있다.
환경은 존재하지만 배포 브랜치 제한은 아직 없다. 따라서 인증 상태는
`AUTHENTICATION_NOT_CONFIGURED`, 신뢰 배포는 `NOT_DEPLOYED`다.
무료 CPU 할당/잔여 시간은 `UNKNOWN`이다. 공식 읽기 API의 GPU/TPU quota를
CPU quota 수치로 바꾸어 주장하지 않는다. CPU 요청에는 accelerator/유료 machine shape를
넣지 않으며, 계정 자격과 실제 허용 여부는 제공자 응답으로 확인해야 한다.
GPU 제어 실험은 CPU 실제 수용 시험 이후로 남는다.

원래 main은 0192이고 과학 개발 스택은 0202까지다. 별도 최소 배포 PR은 컨트롤러
파일만 main에 배포하도록 준비한다. 기존 연속성 규칙은 모든 일반 PR에 순차 체크포인트와
CURRENT 갱신을 요구하므로, 스택을 병합하지 않는 최소 배포에는 소유자가 승인한
명시적 연속성 처리 결정이 필요하다. 이 검사를 우회하거나 전체 스택을 몰래 병합하지 않는다.

공식 인터페이스 근거:
- https://github.com/Kaggle/kaggle-cli/tree/5da4593737d65353ff35ce402ff2e918c2c780f3
- https://github.com/Kaggle/kaggle-cli/blob/v2.2.5/docs/kernels.md
- https://github.com/Kaggle/kaggle-cli/blob/v2.2.5/README.md
- https://docs.github.com/en/rest/git/refs
- https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases

컨트롤러의 reconcile 및 publish는 이제 원장 브랜치 보호를 GitHub API에서 직접
조회한다. 강제 푸시와 삭제가 금지되고 관리자에게도 규칙이 적용되어야 한다.
보호 상태가 없거나 조회 권한이 없으면 원장 변경 및 Kaggle 제출 전에 실패한다.
읽기 전용 preflight는 원장 생성이나 Kaggle 제출 없이 별도로 실행할 수 있다.
2026-10-27 확인: 현재 `kaggle-production`에는 배포 브랜치 제한이 없으며,
원장 보호와 저장소 Secret/Variable 목록 조회는 GitHub API 403으로 확인하지 못했다.
과거 인증 기록은 현재 토큰이나 계정 인증의 증거가 아니다.
