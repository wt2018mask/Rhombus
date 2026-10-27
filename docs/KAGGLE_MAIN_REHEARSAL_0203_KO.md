# 0203 main 기반 격리 배포 재현

2026-10-28. 기준 main `1aaaa555a9a1ce2c9123845402fec4e664626708`(0192),
검토 대상 0203 `c7ecf24ed178cddce2e77d0cc06fb714c1b6ea7d`. 생산 NO-GO.

## 실제 관측

별도 `/tmp`에 공개 main을 새 clone하고 0203의 커밋된 `rhombus/automation/` 11개
파일만 복사했다. `python -S`로 기존 editable 설치를 배제하고, 격리 checkout과
고정 버전 Kaggle SDK의 site-packages만 사용했다. 자동화 모듈 import, kaggle 2.2.5 /
kagglesdk 0.1.38, 고정 request 및 policy digest는 PASS다. 토큰을 전달하지 않았으며,
인증 누락·없는 원장·원장 ref 생성 시도·보호 API 403은 모의 객체에서 실패했다.
제공자 호출과 과학 계산은 0이다. `python -m scripts.tools.rehearse_kaggle_minimal`로
이 오프라인 재현을 다시 수행할 수 있다. 일부 테스트는 모의 응답이며 production
권한·ruleset·실제 Kaggle 인증의 증거가 아니다.

main에는 `rhombus.atomistics.thermal_study`가 없으므로 독립 과학 검증에는 workflow가
고정 커밋의 별도 checkout을 가져와야 한다. 추가로 main의 `rhombus/tools/mcp_server.py`는
`additional_tool_specs` 인자를 지원하지 않는다. 최소 11파일만 복사한 환경에서 실제
`create_server()`는 TypeError다. 0203 HEAD의 커밋된 `rhombus/tools/mcp_server.py`를
추가해 다시 실행하면 server 생성은 PASS다. MCP 사용이 필수인 배포 후보는 이 파일,
MCP 2.3.0 및 jsonschema를 포함해야 하며 six-tool 행동과 실제 stdio 회귀를 재검토한다.
단순 import 성공만으로 transitive 전체 또는 배포 성공을 주장하지 않는다.

새 공개 main clone에서 science SHA `474df8faa7484b87f19e5679336192939598e1f7`를
직접 fetch했고, `refs/heads/worker/k202` fetch도 같은 SHA를 반환했다. 별도 checkout을
만들어 request inventory **283개 소스 파일** 및 0200 report와 **20개 raw artifact**의
실제 체크아웃 바이트 SHA256을 전부 확인했다. 존재하지 않는 SHA는 실패했다.
한 로컬 shallow clone은 대상 tree를 전달하지 않아 checkout이 실패했으며 공개 GitHub에
명시적 SHA fetch한 뒤 성공했다. 명시적 fetch의 오늘 성공은 GitHub Actions/Kaggle의
향후 접근성이나 해당 브랜치의 불변·영구 보존을 보증하지 않는다. `worker/k202`는
일반 브랜치로, 독립 승인·보호된 immutable ref로 검증되지 않았다.

workflow 두 개는 YAML으로 파싱됐고, 전체 기존 과학/컨트롤러 회귀는 현재 개발 checkout에서
별도 실행했다. 격리 main에서 실제 provider 인증, submit, GitHub admin, 전체 science verifier
실행이나 GitHub release 게시를 수행하지 않았다. 이들 각각의 production readiness는 미확인이다.

## 두 통합 방식

**A — 검토된 stack**: main SHA에서 PR #363, #364, #365, #367, #369, #371, #370,
#372, #373, #374, #375의 실제 계보와 이벤트 0193–0203을 순서대로 검토한다. 0202까지
`worker/k202`는 main보다 88 commits 앞선다. c7ecf24까지 main 대비 실제 파일별 변경은
[KAGGLE_STACK_DIFF_0203.txt](KAGGLE_STACK_DIFF_0203.txt), 233파일이며 각 파일의 과학적
의미, frozen 자료, 외부 원문 및 전체/전용 CI를 따로 평가해야 한다. `STACK_REPAIR`는
정확한 base SHA와 0193–0203 전체 연속 이벤트를 요구한다. 단순 stack merge가 모든 과학
PR의 독립 검증과 main 병합을 승인하는 것은 아니다. 현재 원문 CI 실패2건과 별도 보호·권한
조건이 남아 있으므로 무심코 통합할 수 없다.

**B — 별도 최소 controller**: main 0192에서 기존 일반 PR 규칙에 맞는 새로운 0193 이벤트와
CURRENT/HANDOFF를 작성하고 11개 automation 파일, 두 workflow, 필요한 검증/테스트와 MCP를
제공하는 경우를 검토할 수 있다. 단, 기존 stack의 실제 0193과 서로 다른 이벤트를 같은
순번으로 만들게 되므로 이후 역사 통합에 충돌한다. 생략한 0193–0203을 배포 완료로 기록하거나
`STACK_REPAIR` 예외로 우회할 수 없다. frozen checkout 283파일/20자료 및 그 ref의 장기
접근, main에 없는 MCP 인터페이스, main 전용 환경, 원장 root SHA·보호·단일 작성자,
독립 감사 권한 및 검증된 secret을 확보해야 한다. 재현된 최소 controller import와 MCP
서버 생성은 유망하지만 완전한 독립 배포 성공이나 승인 근거는 아니다.

**선택: 현재 둘 다 배포 NO-GO.** 파일 범위만 보면 B가 작지만 0193 충돌과 나중의 이력
통합 방식을 소유자가 결정해야 한다. A는 기존 과학 이력을 보존하지만 233파일 전체와 관련
과학·CI 검토/승인이 필요하다. owner 결정과 해당 검증 전에는 별도 배포 PR을 만들지 않는다.
기존 #375는 검토용으로 유지한다. main merge·활성화·원장 변경·Kaggle preflight/submit은
각각 별도 승인 대상이다.

## 승인 후 실행 및 독립 확인

이미 확인한 것: 고정 Git bytes·로컬 mock 경합/실패·74개 관련 로컬 테스트와 격리 재현.
승인 후 자동화 가능한 것: main 전용 환경 구성, 생성 전 원장 보호와 root provisioning,
정확한 정책/root SHA 등록, read-only preflight. 각각 실제 관리자/GitHub App 권한과 별도
승인이 필요하며, 응답 유실 시 재조회하고 맹목적 재시도하지 않는다.
production identity 없이는 실효 ruleset, bypass actor, 단일 writer, secret 존재, Kaggle
인증·quota를 확인할 수 없다. 최소 권한은 실제 GitHub API 및 해당 identity로 검증하며,
403은 계속 UNVERIFIED다. secret 값을 채팅이나 CI에 노출하지 않는다.

정책 SHA `921f430a7e2435c763760f9ac866306c15ac7dc14572353ca76b4a2d682a1ea2`
및 CPU/비용/1회 한도는 변경하지 않았다. 원장·환경·main을 수정하지 않았고 Kaggle 실행은 없다.
