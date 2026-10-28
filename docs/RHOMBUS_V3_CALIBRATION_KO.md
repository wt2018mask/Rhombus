# Rhombus 3.0: 실제 좌표 계산과 미확립 보정 경계

이번 작업은 제공된 상수를 코드에 고정하고 실제 저장 CIF에서 계산했다.
**요청한 γ-LiAlO₂ 고장벽 판별은 재현되지 않았다. 15개 항목 전체 과학 완료나
authoritative qualification 완료를 선언할 수 없다.** 계수와 임계값을 원하는
순서에 맞춰 변경하지 않았다. 모든 최종 qualification은 ABSTAIN이다.

계산 보고서와 실제 생성 portfolio는
[content-addressed evidence index](../data/benchmarks/v3_static/owner_constants_v1/README.md)에
보존했다. 코드 commit, 파일 SHA256 및 수치 잔차를 함께 확인할 수 있다.

## 실제 계산 결과

기본 24³ 격자, Morse + screened-Coulomb, screening factor=1,
effective charge scale=1, Pauli 항 OFF, 한 이동 이온/고정 호스트 NEB다.
1 eV 정적/MEP 기각 기준은 **잠정 정책**이며 도메인 보정된 물리 기준이 아니다.
아래 장벽은 이 모델의 계산값이지 MACE/DFT/실험 활성화 에너지가 아니다.
반경은 minimax witness의 격자점 여유도이며 연속 경로 병목의 수렴값이 아니다.

| 구조 / 원자 수 | 3D 격자 장벽 eV | 격자 병목 Å | NEB raw 장벽 eV | NEB 수렴 | 잠정 정적 정책 |
|---|---:|---:|---:|---|---|
| γ-LiAlO₂, COD 1008166 / 16 | 0.613769014 | 0.425822781 | 1.114553591 | 아니오 | PASS_P0_5 |
| Li₂S, COD 9009060 / 12 | 1.159297777 | 0.490281242 | 5.584680254 | 예 | FALSIFIED_HIGH_STATIC_BARRIER |
| tetragonal LLZO, 저장 CIF / 192 | 2.733248182 | 0.218872541 | 1.289645973 | 예 | FALSIFIED_HIGH_STATIC_BARRIER |
| Li₂S 2×2×2 / 96 | 0.710491689 | 0.490281242 | 5.331975498 | 예 | PASS_P0_5 |
| 같은 셀의 Li 단일 공공 probe / 95 | 0.710491689 | 0.490281242 | 5.331975498 | 예 | PASS_P0_5 |
| Li₂S→Cl 치환 + Li 공공 제안 / 95 | 0.710615868 | 0.490281242 | 0.763356944 | 아니오 | PASS_P0_5 |
| LLZO→Ta 치환 + Li 공공 제안 / 191 | 2.737444938 | 0.218872541 | 1.921468021 | 아니오 | FALSIFIED_HIGH_STATIC_BARRIER |
| **가상** Li₃YCl₆ 원형→Zr 치환 + Li 공공 / 79 | 0.595688148 | 0.495548862 | 0.118718551 | 예 | PASS_P0_5 |

모든 행에서 실제 `ΔE_hull`과 `[V_red,V_ox]`는 **null**이다. 같은 에너지
모델로 계산한 원소/경쟁상 에너지가 없어 값을 만들지 않았다. 최종 gate는 모두
ABSTAIN이다. 미수렴 NEB raw 값은 검증된 MEP barrier로 사용하지 않는다.
수렴한 한 초기 경로도 전역 최저 경로 증명이 아니다.

제공된 a=5.1687 Å, c=6.2679 Å는 저장 COD의 5.17 Å, 6.295 Å와 다르다.
기존 CIF를 해당 값으로 몰래 변경하지 않았다. 새로운 γ 상의 독립 원자 좌표는
첨부에 없었으므로 임의 좌표로 다른 '실제 결정'을 만들지 않았다.
Li₃MCl₆의 원자 좌표도 제공되지 않았다. 따라서 halide는 명시적으로 가상
원형이며 실제 Li₃YCl₆ 또는 고속 전도체 검증으로 부를 수 없다. 저장된
**tetragonal** LLZO를 고속 **cubic** LLZO로 부르지 않는다.

32³에서 γ-LiAlO₂ 장벽은 0.539638845 eV, 병목 0.427512556 Å이고 Li₂S는
1.181802312 eV, 0.430343098 Å다. 격자·경로 수렴은 확립되지 않았다.
단위셀과 supercell 사이에는 최근접 이미지 host 합과 표본화 간격에 따른
차이가 있다. 이 모델에서 이동 Li를 제거하므로 같은 셀의 Li 공공 자체는
host 에너지장을 바꾸지 않는다. 공공 생성이 정적 장벽을 낮춘다는 테스트를
만들 수 없다. 또한 공공이 없는 결정도 interstitialcy/협동 이동을 할 수 있어
본 funnel의 공공 요구는 제한된 vacancy-hop 연구 정책이지 보편적인 확산 법칙이 아니다.

## 15개 완료 기준에 대한 상태

| 항목 | 구현/검증 상태 | 남은 과학 또는 실행 경계 |
|---|---|---|
| 1. 상수 registry | 첨부된 8개 음이온·13개 framework 양이온 수치와 SHA256 고정 | 원문 표/페이지, CN별 반경 적용성 미인증 |
| 2. 실제 CIF 정적 장벽 | COD 2개·tetragonal LLZO·결함 구조에서 실제 계산 | 요구 판별 실패, continuum/cell 수렴 미확립 |
| 3. 실제 좌표 NEB | 모든 표 행에서 실행·잔차/수렴 보존 | 일부 미수렴, 전역 MEP 및 MLIP 검증 아님 |
| 4. supercell | 역격자 plane spacing도 9.5 Å 이상, atom cap | 유한 크기 결함 수렴 별도 |
| 5. intrinsic vacancy | 대칭 독립 Li 공공 Ewald 순위·실제 빈 좌표 | 단독 Li 공공은 −1 charged probe, 생성 에너지 아님 |
| 6. aliovalent doping | Zr→Ta, S→Cl, Y→Zr 및 명시적 Li interstitial 보상 | 제한된 orderings의 Ewald 순위, 합성 가능성 아님 |
| 7. fractional ordering | 정수 조성 보존·bounded exhaustive Ewald 순위 | 큰 조합 공간은 명확히 거절, 전역 대규모 ordering 미구현 |
| 8. electronic P0 | open-d/mixed valence 기각, 환원 위험 flag | 조성으로 bandgap/MIEC를 증명할 수 없어 Eg=null |
| 9. hull P1 | 동일 모델·원소 endmember 요구, 30/80/>100 meV 문턱 테스트 | 실제 후보의 경쟁상 에너지 없음, 80–100 구간 기권 |
| 10. ESW S | chemical-potential LP와 분해 반응 생성물 분류 | 실제 에너지 없음, kinetics/SEI 전자전도 증명 아님 |
| 11. generator | 3개 domain의 전하 보상 구조·명시적 utility | 새 결정 발견 아님, halide 좌표 가상 |
| 12. 통합 funnel | 실제 G/P0/static/hull/MEP/transport/X/S 기본 adapter | 원격 측정 없으면 중단, 자격 승격 금지 |
| 13. Kaggle worker | source/protocol/model 검증, CPU, canonical P2/P2.5 연결 | 실제 Kaggle/MACE 실행 미검증·미제출 |
| 14. 80% seal/import | 단계·궤적별 SHA256/fsync, partial/failure, 중복 시도 거절 | cooperative guard; 멈춘 native force call 강제 중단 보장 아님 |
| 15. MCP 3.0 | 6+3 또는 기존 automation 8+3 additive 도구 테스트 | 호스트 준비 proposal/dossier 조회, 원격 실행 권한 없음 |

## 공개 API와 함수 시그니처

- `transport/bvse_parameters.py`: `parameter_identity()`,
  `build_site_evaluator(structure, *, screening_factor=1., effective_charge_scale=1.)`.
  `R_min`을 bond-valence 식의 `R_0`와 혼동하지 않는다. '문헌 인용 주장'과
  '원문 검증'을 분리한다. Pauli 없는 새 evaluator 경로이며 기존 기본 동작은 유지한다.
- `transport/static_assessment.py`: `assess_static_transport(structure, *,
  grid_dimension=24, screening_factor=1., effective_charge_scale=1.,
  max_barrier_eV=1., run_mep=True, vacancy_fractional_target=None, mep_steps=200)`.
- `generation/defect_engine.py`: `expand_supercell(structure, *, minimum_length_A=9.5,
  max_atoms=512)`, `seed_vacancies(structure, *, minimum_length_A=9.5, top_k=1,
  max_configurations=32, charges=None)`, `substitute_aliovalent(structure, *,
  site_index, dopant, dopant_charge, interstitial_fractional=None, top_k=1,
  max_configurations=64, charges=None)`, `order_fractional(structure, *, top_k=1,
  max_configurations=128)`.
- `qualification/electronic_insulation.py`: `assess_electronic_insulation(structure, *, charges=None)`.
- `atomistics/phase_stability_p1.py`: `assess_phase_stability(candidate, references)`.
  entry는 `composition`, total `energy_eV`, `energy_model_id`, `reference_id`를 요구한다.
- `qualification/electrochemical_window.py`: `assess_electrochemical_window(candidate, references)`.
  모든 reference는 같은 chemical space/model이어야 하며 서로 다른 MLIP/DFT 영점을 섞지 않는다.
- `generation/autonomous_generator.py`: `AutonomousCandidateGenerator(templates=None).generate(*,
  domains=('O_ONLY','S_ONLY','HALIDE'), top_k=6, minimum_length_A=9.5)`.
  `selection_utility(*, atom_count, static_barrier_eV=None, hull_meV_atom=None,
  window_width_V=None, epistemic_uncertainty=1.)`는 계산 우선순위일 뿐 과학 fitness가 아니다.
- `pipeline/funnel.py`: `RhombusDiscoveryFunnel(adapters=None).run(candidate)`.
  기존 8단계 custom adapter API는 유지한다. 기본 경로는 G→P0→P0.5→P1→P1.5→P2→P2.5→P3→X→S.
  공공은 parent Li 좌표와 child의 실제 빈 위치를 비교한다. 불충분하거나 charged이면 중단한다.
- `automation/campaign_worker_v3.py`: `prepare_campaign_request(repository, revision,
  candidates, protocol)`, `run_on_kaggle(request, output_dir, *, repository,
  owner_launch=False)`, `verify_campaign(directory, *, expected_manifest_sha256)`.
  `CampaignWorker(...).run(candidates, evaluate)`와 `checkpoint(unit=None)`는 신뢰된
  호스트 callable용이며 MCP에서 임의 callable을 받지 않는다.
- `atomistics/campaign_dynamics.py`: `KaggleMACEStages(protocol, *, checkpoint,
  output_dir, binding)`, `block_diffusivity(unwrapped_mobile, times_ps, *, seed,
  blocks=4, bootstrap=200)`. canonical P2/P2.5 문턱을 변경하지 않고 host-subtracted
  MSD와 block-origin D 분산을 추가한다. P1은 현재 고정 셀 원자 이완이다.
- `mcp/catalog_v3.py`: `build_portfolio_catalog(candidates, dossiers=())`,
  `create_server(evidence_snapshot, *, portfolio_path, expected_sha256, github=None)`.
  `generate_candidates_v3`, `evaluate_funnel_v3`, `query_portfolio_catalog_v3`는
  호스트가 준비한 결과를 조회한다. 코드·경로·임의 실행 요청 인자는 거절한다.

## 실행과 검증

새 과학 코드에는 새 V3 request를 만들어야 한다. 기존 0201/0202/0203 request,
자동 제출 정책, 모델 해시, 원장, historical checkpoint는 바꾸지 않았다.
`prepare_campaign_request`는 **이미 커밋된 새 source SHA**의 inventory를 만든다.
`protocol`에는 `mode`, `wall_seconds`를 명시한다. MACE mode에는 input model path,
정확한 model SHA, runtime pins(torch/mace-torch/numpy/ase/pymatgen), 3–6개 온도,
온도 범위 ≥150 K, 2–4개 seed, 제한된 MD/relaxation/MEP 설정을 추가해야 한다.
이를 임의로 기존 frozen 0201 재현이라고 부를 수 없다. 실제 model 입력은
`/kaggle/input`에서 complete SHA256 검증 후에만 deserialization한다.
task ID별 exclusive 소비 마커로 같은 Kaggle runtime의 다른 출력 경로를 통한
중복 시도도 거절한다. runtime이 초기화되면 이 마커는 사라지므로 notebook
버전 사이의 전역 중복 방지나 trusted-host atomic consumption 증거는 아니다.

수동 Kaggle CPU 안에서만 다음을 실행할 수 있다. 이 문서는 실행 승인이거나
할당량 증거가 아니며 이번에는 **어떤 작업도 제출하지 않았다**.

```sh
python -m rhombus.automation.campaign_worker_v3 --request request-v3.json --output /kaggle/working/result-v3 --owner-launch
```

`result-v3` 전체를 보관한다. `manifest.json`, 모든 번호/hash JSON receipt,
`artifacts/`의 thermal JSON과 trajectory NPZ를 함께 내려받아야 한다.
manifest digest를 별도로 보관한 뒤 모델 없이 무결성 검사할 수 있다:

```sh
python -m rhombus.automation.campaign_worker_v3 --request request-v3.json --output result-v3 --verify-manifest-sha256 SHA256
```

이 명령은 byte integrity와 상태 검증이다. 독립적인 provider 인증이나 완전한
offline 과학 재계산 importer가 아니다. 기존 0201 importer로 V3 결과가 자동
인증된다고 주장하지 않는다. source와 thermal/trajectory binding을 포함한 V3
독립 과학 import는 별도 검증이 더 필요하다. `OWNER_MANUAL_LAUNCH`와
`PROVIDER_ATTESTATION_UNAVAILABLE`을 유지한다.

이번에 로컬에서 실행한 것은 명시적으로 요청된 bounded static/Ewald/NEB 계산과
수치 테스트뿐이다. MACE·relaxation·MD는 실행하지 않았다.
`REMOTE_SCIENCE_NOT_EXECUTED`; production OFF, 자동 제출 금지, main 미병합.
