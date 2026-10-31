# RHOMBUS 0204 — Tier A 모델 체크포인트 공급망 검증 (5차 개발)

2026-10-31 · 대상: `worker/k204-evidence-qualified-strategy` (`25e35999e3dd6ca8521838706acd5bb534ad13d7`)

## 판정

`TIER_A_PROTOCOL_DRAFT_READY` / `BENCHMARK_NOT_FROZEN` / `TIER_B_NOT_FROZEN` / `SCIENTIFIC_NO_GO_ABSTAIN`.

이번 변경은 모델 가중치 파일을 다운로드·역직렬화·실행하지 않는 **오프라인 공급망 진단**이다. 실제 MACE/DFT/NEB/MD/계산/성능 scoring은 0회이며, GitHub의 CURRENT/HANDOFF/기존 체크포인트/역사적 증거는 수정하지 않는다. 개발 코드는 아직 GitHub에 통합되지 않았다.

## 새로운 확인 사실: 공식 릴리스 크기와 외부 SHA256 보고

공식 GitHub Release API (2026-10-31 조회, `ACEsuit/mace-foundations`)가 제공하는 자산 메타데이터:

| 구분 | tag | asset ID | 크기 | Release API SHA256 |
|---|---|---:|---:|---|
| MACE-MP-0 small | `mace_mp_0` | 145021750 | 32,581,838 bytes | **null** |
| MACE-MPA-0 medium | `mace_mpa_0` | 213937064 | 79,462,305 bytes | **null** |

- small 릴리스 자산의 파일명은 `2023-12-10-mace-128-L0_energy_epoch-249.model`.
- medium 릴리스 자산의 파일명은 `mace-mpa-0-medium.model`.
- 공식 MACE 소스 `mace/calculators/foundations_models.py` (`e37c8583a8b1b586e5888fa6dca86e8f591e2606`)의 `mace_mp(model='small')` 대응 모델은 해당 small 릴리스 파일이며, MPA-0 medium과 다른 모델이다. `ACEsuit/mace-mp` 주소는 지금 `ACEsuit/mace-foundations`로 옮겨진 저장소의 구 주소다.
- 유럽 고성능컴퓨팅 교육 자료 ENCCS의 MACE 모델 강의는 정확히 위 파일명과 **32,581,838 bytes** 및 `2ddb079cee0e131eaaf6912ba581b394551ead283e95c99cfe78c605d10b5736` SHA256을 보고한다.
  - https://enccs.github.io/mlip-hands-on/episodes/01-model.html (model.toml, 44–55행)
- 기존 Rhombus 0200은 MACE-MPA-0 medium의 79,462,305 bytes SHA256 `75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638`을 보고했다.

**중요:** 공식 GitHub 릴리스 자산 API는 위 모델의 SHA256을 제공하지 않는다. ENCCS의 small SHA256은 **외부 3자 기록**이며, 배포자 공식 서명·독립 인증이 아니다. 이번 환경에서 두 `.model` 파일을 실제로 확보하지 못했다. 따라서 현재 Rhombus의 small checkpoint는 *외부 SHA256 후보를 발견했지만 로컬 파일 바이트로 확인하지 않은 상태*이고, owner-approved pinned baseline으로 승격하지 않는다.

## 신규 코드

- `rhombus/benchmark/tier_a_checkpoint_supply.py`: source-typed 모델 자산 인벤토리 + 실제 파일 제공 시 파일 크기·SHA256 검사. 모델을 로드하지 않음. 보고서는 `.model` 로컬 경로와 어떤 성능값도 표시하지 않음.
- `scripts/benchmark/inspect_tier_a_supply_0204.py`: 기존 Tier A 4개 TRAIN 초기 경로가 고정된 비실행 비용 draft를 입력으로 읽어 공급망 보고서를 생성. 기본 실행은 파일 없이 메타데이터만 검사. 출력 덮어쓰기 및 입력 파일 출력 경로 충돌 거부.
- `make_small_digest_candidate`: 사용자가 실제 small 모델 파일을 제공한 경우, ENCCS 보고 SHA256와 **32,581,838 bytes**를 다시 계산·검증한 후에만 실행 권한 `false`인 *candidate* draft를 반환. 증거 JSON을 위조하거나 기존 report만 조작해도 실제 local model file 재해시를 생략할 수 없음. 이 기능으로 동결·성능 보증·실행 승인은 얻지 못함.
- `tests/test_tier_a_checkpoint_supply_0204.py`: 위조 JSON·가짜 모델·SHA 불일치·크기 불일치·심볼릭 링크·다운로드 없이 파일 미제공·출력 덮어쓰기·target 필드 주입 등 음성 테스트.

재현 명령 (MACE 파일이 없어도 동작):

```bash
python -m scripts.benchmark.inspect_tier_a_supply_0204 \
  --draft /path/to/tier_a_equal_budget_input_pinned_DRAFT_NOT_AUTHORIZED.json \
  --report /new/dir/tier_a_checkpoint_supply_NON_EXECUTABLE.json
```

`--small-model`과 `--medium-model` 옵션에 실제 파일이 있으면 그 파일을 **바이트만 읽어** 검증한다. 자동 다운로드와 계산은 없다. `--candidate-draft`는 실제 small 파일이 검증된 경우에만 사용 가능하고 여전히 실행 불가 상태다.

## 나머지 결정적 미해결 사항

1. small의 **실제 배포 파일 32,581,838 bytes**를 소유자가 직접 확보하거나 신뢰된 다운로드 환경에서 제공해야 로컬 SHA를 재검증할 수 있다. 이때 배포자가 실제 제공한 SHA가 ENCCS와 다르면 임의로 무시하지 않고 중단한다.
2. medium은 기록된 SHA가 있으나 이번 환경에는 파일 자체가 없으므로 재검증하지 못했다.
3. 정확한 공통 NEB 수치 규칙은 여전히 `SUGGESTED_NEB_NOT_FROZEN` 단계이며 비용 상한 및 수렴/실패 처리의 소유자 승인이 필요하다.
4. 동일·독립 MACE 사전학습 노출, DFT reference의 행별 전자 계산 조건, 독립적인 source-out 검증은 해결되지 않았다.
5. 실제 계산 비용·성능·오차·coverage·false-accept risk 데이터가 **전혀 새로 생성되지 않았다**.

## 완료 기준과 권한

이번 완료 기준은 source-typed catalog, 실제 파일 검사 코드, 모델 역할 분리, 오프라인 report, 음성 테스트, 바이트 재현성이다. 위 두 파일 모델을 확보하지 못했다는 이유로 거짓 자격을 부여하지 않는다. 소유자의 **별도 명시적인 계산 승인 없이는** 단 한 번의 MACE/NEB 계산도 시작하지 않는다.
