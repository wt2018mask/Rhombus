# 0203 통합 결정 및 격리 릴리스 후보

2026-10-28. 이 문서는 통합 경로에 대한 권고이며 배포·merge·preflight·계산 승인이 아니다.
main은 `1aaaa555a9a1ce2c9123845402fec4e664626708`(0192), 평가 시작 0203 HEAD는
`a99d3f62f7a89f272860f340161f60fa5735cdd0`다. production 및 preflight는 NO-GO다.

## 권고: A, 기존 stack의 순차적 검토

A는 실제 checkpoint 이력을 유지하므로 **A를 우선 권고**한다. 검토 순서는 다음이다.
각 PR과 정확한 SHA, 과학 근거·보안·전용 CI를 독립 검토한다. Git 계보는 과학 승인이나
main merge 승인이 아니다.

| 순서 | PR | 확인한 head | base |
| --- | --- | --- | --- |
| 0193 | #363 | `3c2f42f6f5c3c88acfb55fcd6cdf7acab8b76802` | main |
| 0194 | #364 | `03c1bd5b1ba37284d73577c8fd58e4382b0d4251` | #363 |
| 0195 | #365 | `e3547d9968ce44a39b1d084f5440082d9e982d66` | #364 |
| 0196 | #367 | `afbe238287b6321190af2e263f5afdf100c3ca0c` | #365 |
| 0197 | #369 | `87446af01baefa4b1dc5e4f592012dca591ef795` | #367 |
| 0198 | #371 | `072d0ccd5d45f41e83e3dd0cfdea6d129c1cc9fe` | #369 |
| 0199 | #370 | `b824a726ef65f350afd7daea0390c8e5eb721a46` | #371 |
| 0200 | #372 | `549c94aa6e9906271e08555d4e20d7449148e6da` | #370 |
| 0201 | #373 | `b16bbebb49440a0b733fc800d16eadd4cc487ff4` | #372 |
| 0202 | #374 | `474df8faa7484b87f19e5679336192939598e1f7` | #373 |
| 0203 | #375 | `a99d3f62f7a89f272860f340161f60fa5735cdd0` at assessment | #374 |

main-to-a99 diff는 237파일, 100 commits다. 기존 c7 기준 233개 파일의 상세 목록은
[KAGGLE_STACK_DIFF_0203.txt](KAGGLE_STACK_DIFF_0203.txt)에 있고, 최신 목록은
`git diff --name-status 1aaaa555a9a1ce2c9123845402fec4e664626708...<reviewed-head>`로 얻는다.
`STACK_REPAIR`는 승인된 예외적 통합에만 사용할 수 있고 정확한 base SHA와 기존 0193–0203
전체 연속 이벤트·참조·state를 보존해야 한다. 공통 CI뿐 아니라 각 과학 PR의 gate와
canonical Wave 2를 평가해야 한다. 이전 HEAD의 실제 원문 획득 검사 두 개는 실패 상태다.
이는 검토 노력과 범위가 크다는 단점이 있지만 기존 과학 checkpoint의 의미를 충돌 없이
유지하는 쪽이다. 각 merge와 실패 해결은 별도 승인·검증이 필요하다.

B는 main 0192에서 controller만 배포하는 방안이다. 파일 범위는 줄지만 새 0193 이벤트가
기존 stack의 진짜 0193과 충돌해 이후 역사를 통합하기 어렵다. 독립 component/release
branch는 별도 승인된 향후 이력 정책과 trust boundary가 필요하며, 새 저장소/서비스를
기본 요구로 추가할 근거는 없다. frozen commit 접근과 모든 보호·provider gate도 여전히
필요하다. 현행 validator 예외나 이벤트 재해석 없이 B가 장기 통합까지 해결됐다고
입증되지 않았으므로 배포 PR을 만들지 않았다.

## 독립 격리 후보와 검증

다음은 **검토용 후보 생성기**다. 기존 main을 건드리지 않고 Git commit의 바이트만 복사하며
production-ready 여부를 주장하지 않는다. destination은 새 디렉터리여야 한다.

```bash
python -m scripts.tools.build_release_candidate_0203 \\
  --source-commit a99d3f62f7a89f272860f340161f60fa5735cdd0 \\
  --destination /tmp/new-rhombus-release-candidate
```

출력 JSON에 각 경로와 SHA256이 있다. 후보는 main snapshot 위에 다음 16개 파일을 적용한다:
`rhombus/automation/`의 9개 Python 모듈과 `policy.json`, `request.json`(11개),
`rhombus/tools/mcp_server.py`, `scripts/tools/kaggle_0203_readiness.py`,
`scripts/tools/validate_kaggle_bootstrap.py`, 두 `kaggle-thermal-controller.yml` /
`kaggle-automation-tests.yml` workflow. workflow 테스트 파일과 다른 CI/연속성 변경은
**후보에 포함되지 않아** 이 16개만으로 독립 배포 PR이나 전체 CI가 성립한다고 주장하지
않는다. frozen science 및 output 자료는 별도 checkout이며 추가한다면 별도 검토가 필요하다.

fresh main checkout과 별도 Python 3.11 venv에 `kaggle==2.2.5`, `kagglesdk==0.1.38`,
`mcp==2.3.0`, constraints를 적용한 pytest/numpy/scipy/ASE/pymatgen/smact/pyyaml을 일반
설치했다. editable 프로젝트 설치는 하지 않았다. candidate의 `policy-digest`가 승인값과
일치했고 readiness는 NO-GO/exit 1이다. 실제 MCP stdio에서 기존 6개 이름과 빈 후보 조회의
`claim_authorized=false`를 확인했으며, candidate 자동화 서버 등록은 8개 도구를 내놓고
mock GitHub 호출은 0이었다. 이는 여섯 도구의 모든 행동·인증된 production 경로가 검증됐다는
뜻은 아니다. 별도 frozen checkout의 `rhombus.atomistics.thermal_study` import와 누락된
과학 증거 거부도 확인했다. 실제 Kaggle·GitHub 관리자 요청이나 모델 계산은 수행하지 않았다.

별도 가상환경의 관련 테스트 75개 및 continuity가 통과했다. 0203 출발 HEAD의 CI는 57개
성공과 기존 원문 획득 2개 실패였다. mock 권한/공급자 응답은 실제 production 인증이 아니다.

## 고정 science 보존

`474df8faa7484b87f19e5679336192939598e1f7`은 관측 시점 `worker/k202`의 HEAD이고
`worker/k203-automation`의 조상이다. `worker/thermal-0201`은 그 커밋의 조상이므로 이
커밋을 보존하는 ref가 아니다. 이들 개발 branch는 불변 보존으로 인증되지 않았다.
새 clone의 SHA fetch 및 branch fetch, 별도 checkout의 283개 source/20개 기존 artifact 해시가
통과했지만 향후 retention 및 Actions/Kaggle 권한은 미확인이다. workflow와 Kaggle worker는
각각 정확한 SHA를 checkout하고 request inventory/model digest를 검증한다. 조회가 실패하면
다른 revision으로 자동 전환하지 않는다.

후보 보존안은 소유자 승인 후 별도 보호된 고정 ref를 만들고 독립 감사자가 변경·삭제·bypass
제한 및 정확한 SHA를 검증하는 것이다. release asset은 삭제·변경 가능성이 있으므로 보호/
불변성과 raw inventory digest를 증명하지 못하면 동등한 보존 증거가 아니다. 실제 ref 또는
release는 만들지 않았다. 로컬 재검증:

```bash
python -m scripts.tools.kaggle_deployment_inventory > /tmp/science-inventory.json
```

## 소유자 결정의 정확한 범위

선택할 다음 행동은 **A의 각 PR 검토 및 blocker 정리 작업을 계속할지**다. 예시 승인 문구:

> 기존 0193–0203 stack을 순서대로 검토하고 과학·CI·보안 차단 요인을 정리하는 작업을 승인합니다.
> 이 승인은 main merge, production 설정이나 secret 변경, 원장 생성, Kaggle preflight,
> 자동화 활성화 또는 Kaggle 계산을 승인하지 않습니다.

이 검토는 이미 승인된 비파괴 작업 범위에서도 계속할 수 있다. merge나 production 변경은
구체적인 검토 결과가 나온 뒤 각각 별도 승인해야 한다. 실제 production identity로
main 전용 환경, 실효 ruleset·관리자/actor bypass·단일 writer, 독립 root, `RHOMBUS_POLICY_SHA256`,
기존 `KAGGLE_API_TOKEN`의 유효성 및 quota를 확인하기 전에는 배포와 preflight 모두 NO-GO다.
승인된 policy SHA `921f430a7e2435c763760f9ac866306c15ac7dc14572353ca76b4a2d682a1ea2`,
CPU-only·$0·lifetime 한 번·재시도0, frozen 과학 판단은 유지된다.
