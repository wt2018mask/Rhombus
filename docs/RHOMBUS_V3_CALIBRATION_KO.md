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

## Step A: 주기 이미지·spectator·곡선 경로 보정

Step A 코드는 `5d8d74883907014074c8c99758bb3079f73ec7d7`에 결박했다.
새 MCP 도구, UI/reporting wrapper 또는 workflow 파일은 추가하지 않았다.
기존 bare-host 기본 API와 동결 결과는 유지하고 새 모델을 opt-in으로 분리했다.

- `assess_caged_transport()`는 active Li 하나와 N−1 spectator, 8 Å 주기 이미지
  합/C2 cutoff, 0.22 Å 목표 격자, bounded shell 최소화, 두 번의 Dijkstra
  (minimax 후 해당 문턱에서 integral), FIRE 밴드와 golden-section saddle 평가를 사용한다.
  최근접 이미지만 합산하던 불연속과 셀 표현 의존을 수정했다. shell k=O 20,
  S/Cl 8 eV/Å² 및 최대 0.15 Å는 미보정 모델 입력이지 측정 상수가 아니다.
- 같은 2×2×2 Li₂S에서 bare channel은 모두 0.598999757 eV, spectator hop은
  pristine 0.879110725 eV, 단일 Li 공공 0.737619020 eV다. 두 밴드는 수렴했다.
  공공 쪽 끝점의 잔여 힘은 별도로 기록하며 이 값을 검증된 물리적 MEP로 승격하지 않는다.
- γ-LiAlO₂의 24³/32³ analytic sub-voxel 채널은 0.604602394/0.603496017 eV,
  차이 0.001106376 eV다. 그러나 intrinsic site-energy proxy를 더한 유효 장벽은
  0.435875226 eV로, 요청한 γ 고장벽 기각은 여전히 지지되지 않는다.
  1/2 site-energy 차이를 참 Frenkel 형성 에너지 또는 보편적 0.65–0.95 eV로
  주장하지 않는다. 복수 국소 경로·끝점 정상성·전역 MEP의 차이도 보존한다.
- `reference_phases.py`는 요청한 화합물 35개와 원소 14개를 formation-energy
  prior로 제공한다. MACE 절대에너지/raw Ewald 혼합을 거절한다. Endmember 최저
  혼합으로 추정한 hull=0은 안정성 증거가 아니라 구성상 동어반복인 prior다.
  이 표에서 Li₆PS₅Cl은 hull 위 15.7692 meV/atom이므로 평형 ESW는 빈 집합 `[]`다.
  비어 있는 물리적 구간을 임의 숫자나 [0,0]으로 치환하지 않았다.
- `archetypes.py`는 저장 CIF와 source-pinned TRAIN 자료를 구분한다. Ta-garnet과
  argyrodite는 무작위 변형된 출처 좌표의 생성 ordering probe이며 실험 원본이 아니다.
  Li₃YCl₆, Zr-Y halide, LiCoO₂의 검증 가능한 원본 좌표는 확보하지 못했다.
  Ta-garnet probe의 선택된 hop도 미수렴이므로 성공이나 고장벽 반증으로 처리하지 않는다.
- `RhombusDiscoveryFunnel(use_default_literature_references=True,
  use_spectator_model=True)`는 명시적 prior/static 경로다. static 판정은 잠정
  모델 screen이며 `QUALIFIED_STATIC_TIER1_SUPERIONIC_CANDIDATE`를 발급하지 않는다.
  미수렴 band의 높은 upper bound만으로 기각하지 않고, 낮은 밴드 장벽도 끝점
  정상성이 없으면 candidate 판정을 기권한다. final qualification은 ABSTAIN이다.

수치 원본: [전체 Step A 계산](../data/benchmarks/v3_static/step_a_results/e63a370e48a0b2ff53914a099c11c5e7edc0bfc7dd191a26f92b97367a254f19.json),
[동일 셀 pristine 비교](../data/benchmarks/v3_static/step_a_results/c7ea0d8a00fbf8a3562e0d897663ec37c63c74a2bf29d9f39b77843a251e63c9.json).
파일명은 SHA256이며 실행 소스·환경·실패·미확보 상태를 보존했다.
검증: R2+Step A **2,323 passed**, 기존 호환 **87 passed**, 최신 Step A 집중
**19 passed**. CURRENT는 **694 bytes**, continuity/check-pr/diff 검사를 통과했다.

## Step A-2: Pauli ordering, stationary endpoints, thermochemical projection

실행 코드는 `c37db2e6147493423da488a05dc044dfc87b9d7b`에 결박했다.
[10행 수치 원본과 실제 모델 좌표](../data/benchmarks/v3_static/step_a2_results/2e054f0865cb544d03b3ce20975410b72e86e54f5897304bbe1fdc974169579a.json)를
보존했다. 파일명은 SHA256이다. 이 결과는 요청한 모든 재료의 물리적 자격 완료가 아니다.

- `order_mobile_sites()`는 1.95 Å 충돌 graph의 최대 독립집합을 MILP로 증명하고,
  고정 Li 수의 feasible ordering에 seeded 1/2-swap Ewald 최적화를 적용한다.
  1.25 Å split cluster는 기록하되, transitive chain을 하나의 자리로 잘못
  합치지 않는다. 이 기하학적 Nmax는 실제 열역학적 공공 농도의 증거가 아니다.
  Ta-garnet은 Nmax=60/NLi=52, 생성 argyrodite는 Nmax=24/NLi=24다.
  해당 모델의 최소 Li–Li 거리는 각각 2.3101/2.7885 Å다.
- `relax_endpoint_local_basin()`은 0.45 Å sphere, trust-step 0.05 Å, 물리적
  force ≤1e-3 eV/Å를 요구하는 projected BFGS다. 경계의 constrained minimum을
  stationary로 바꾸지 않는다. `initialize_relaxed_pathway()`는 이 결과로 Dijkstra를
  시작한다. 10개 모델에서 끝점 정상성은 8개, 밴드까지 함께 수렴한 것은 7개였다.
  수렴 경로의 refined saddle/image 차이 최대는 0.00014983 eV다.
- `assess_vacancy_transport_a2()`는 pristine 구조에서 temporary vacancy를 만들어
  lattice-to-lattice hop을 측정하고, 다른 Hamiltonian의 Frenkel site-energy proxy를
  분리한다. Born amplitude=1 eV, rho=.29 Å, alpha(O)=1/S,Cl=.35, epsilon_r=9는
  명시적인 미보정 모델 입력이다. 주어진 rho/이온 반경만으로 이 계수들이 결정되지는 않는다.
  dielectric attraction은 음의 부호로 기록하며 가능한 double counting도 명시한다.
  이 값들을 맞춰 원하는 1 eV/0.55 eV 결과를 만들지 않았다.
- γ-LiAlO₂/완전 점유 Li₂S/생성 argyrodite에서 Frenkel site-energy 차이가
  음수다. 이를 max(0, E)로 잘랐다고 superionic candidate로 승격하지 않고
  `STATIC_MODEL_INAPPLICABLE_NEGATIVE_FRENKEL_ENERGY`를 반환한다.
  γ 유효 proxy=0.1291 eV, Ta-garnet hop=1.0028 eV, Cl-Li₂S hop=0.6816 eV로
  요청한 재료별 판별 순서는 지지되지 않는다. 일부 밴드·끝점도 미수렴이다.
- 기존 V3 열화학 표는 보존하고 A2 표에서만 Li6PS5Cl=-1.468 eV/atom을 쓴다.
  이는 소유자가 요청한 prior 교체이며 독립 문헌 보정이 아니다. 실제 균형 분해식은
  Li6PS5Cl=Li2S+Li3PS4+LiCl, 기존 tie-line=-1.380769 eV/atom이다.
  A2 창은 [1.5572,2.6858] V로 계산됐다. `include_intrinsic=True`는 strict
  `equilibrium_esw_volts`와 hull-projected `intrinsic_esw_volts`를 함께 반환한다.
  정확한 hull projection도 Li1.96875S의 [2.265,2.265] V를 없애지 못한다.
  1 meV/atom offset은 별도의 sensitivity이며, 폭을 얻기 위한 물리적 근거로 쓰지 않는다.
- `build_archetype_a2(..., allow_idealized_completion=True)`는 불완전한 입력의
  모델 보완을 명시적으로 요구한다. LiCoO₂ 좌표는 완전한 소유자 제공 표지만
  원문 미인증이다. Halide는 ideal hcp completion, argyrodite는 S 좌표의 geometry
  correction 및 가정한 Li cage, Ta-garnet은 제공 framework/COD Li 좌표의 hybrid다.
  이를 DOI가 검증된 실험 원본으로 부르지 않는다. 제공 argyrodite P/S 좌표의
  직접 대칭 확장은 P–S≈4.105 Å이고, 두 halide Cl 예시는 18개가 아닌 14개로 확장된다.

검증: 전체 `pytest -p no:cacheprovider`는 **4681 passed, 6 failed, 18 skipped**
(4705 collected)였다. Moyopy 0.3.4 및 Matbench 고정 source
`26d3a19073df8cb303c7e4849a0d65e74746d9eb`를 준비한 뒤 prototype 2개는 통과했다.
나머지 4개는 부모 HEAD `224a8a32`의 격리 worktree에서도 같은 실패를 재현했다:

- `test_kaggle_minimal_rehearsal.py::test_release_candidate_materializes_only_committed_blobs`
  (기존 기대 inventory 16개, 실제 17개).
- `test_p2_fixcom_contract.py::test_p2_protocol_version_records_explicit_fixcom_contract`.
- `test_p2_ordered_expansion_wave1_admission.py::test_ordered_expansion_wave1_p2_gpu_admission_contract`.
- `test_p2_persist.py::test_h_p2_protocol_constants_frozen`.
  위 3개는 v2 문자열을 기대하지만 기존 runtime은 ASE-units 수정 v3다.

과거 P2 계약이나 테스트 기대값을 이번 물리 작업에 맞춰 바꾸지 않았다. 관련 집중
**82 passed**, 마지막 A2 검증 **20 passed**. CURRENT **694 bytes**, continuity 및
check-pr 통과. 새 MCP/UI/workflow, Kaggle 제출, production 활성화, main 병합은 없다.


## Step A-3: pure-Morse host proxy, distinct basins, dilute-parent ESW

실행 소스: `217828761134253b86bac578f799e5f577d0bc2e`.
[10행 계산 원본·실제 좌표·경로·실행 driver](../data/benchmarks/v3_static/step_a3_results/43575246fc6a256af6fc2bff2d05d068d5203583ea3d693168236d1270be2b1c.json)
파일명은 SHA256이며 실제 실행 모듈 71개의 hash를 해당 Git blob과 대조했다.
A/A-2 결과, 열화학 V3/A2 prior 및 CURRENT의 694 bytes를 바꾸지 않았다.

- `build_softbv_evaluator()`의 새 A3 기본은 native anion Morse와 cation screening
  factor .75다. 추가 Born-Mayer/unscreened contact/anion shell term은 없다.
  A2 함수와 구 Hamiltonian은 역사적 재현용으로 보존했다.
- `assess_vacancy_transport_a3()`는 pristine에서 하나의 Li만 제거한 vacancy
  probe로 lattice-to-lattice migration을 계산한다. 별도의 Frenkel proxy는
  spectator가 없는 host field에서 occupied basin과 독립 interstitial minimum의
  차이다. 후자는 모든 nominal Li에서 1.85 Å, host에서 1.80 Å 이상 떨어져야 한다.
  없으면 3D host saddle fallback임을 명시한다. 음수를 잘라내지 않는다.
- 끝점은 .65 Å soft restraint와 .05 Å trust step으로 완화한다. restrained
  objective가 아닌 실제 물리적 force <=1e-3 eV/Å를 요구한다. nominal/relaxed MIC
  거리 모두 2.00–4.20 Å여야 하고, pristine nominal hop은 2.2–3.8 Å로 제한한다.
  collapsed neighbor는 거부하고 다음 후보의 voxel graph를 탐색한다. 이번 10행은
  band와 끝점 모두 수렴했다. 최대 endpoint force=0.00061194 eV/Å이고 보존 band
  energy 재계산 오차는 0 eV다. 이는 동일 모형의 수치 검증이며 독립 물리 모형 확인은 아니다.
- Argyrodite는 하나의 이상화된 48h orbit (.18,.18,.02), 24 Li/48 candidate site다.
  모든 후보의 최소 Li–Li=1.951982 Å이므로 geometric Nmax=48, x_vac=.50이다.
  실험 원문을 인증한 refinement가 아니며 이 기하학적 분율은 측정된 carrier 농도가 아니다.
  선택 hop은 nominal/relaxed 2.230837/2.229374 Å이며 self-hop이 아니다.
- LiCoO₂의 기존 SG166 builder는 이미 3 R-centering translation과 Z=3를 만족했다.
  Li–O=2.093237 Å, Co–O=1.921021 Å다. in-plane periodic Li를 서로 다른 atom으로
  표현하려고 transport probe만 2×2×1로 확장하며 원래 12-atom cell도 보존한다.
  29.573 eV의 3D host saddle proxy는 layered 구조의 미보정 모형 값이지 centering
  누락의 증거가 아니다. Co3+ formal-valence rejection도 실제 MIEC 전도도 측정이 아니다.
- `dilute_parent_limit=True`는 host 비율·원소 집합이 동일하고 Li deficiency가
  0<x<=.05인 stable-reference parent에만 적용한다. Li1.96875S는 primary intrinsic
  [0,2.265] V 및 `PARENT_PHASE_DILUTE_DEFECT_LIMIT`를 반환한다. strict와 secondary
  `off_stoichiometric_tieline_window_volts`=[2.265,2.265] V는 남긴다. 외래 dopant나
  비희석 결함을 이 근사로 바꾸지 않는다. A3 funnel opt-in도 같은 경로를 사용한다.

| 구조 | x_vac | 채널 eV | spectator 홉 eV | ΔE_Frenkel proxy eV | E_a,eff proxy eV | NEB·끝점 | Hull meV/atom | ESW V | Static |
|---|---:|---:|---:|---:|---:|---|---:|---|---|
| γ-LiAlO₂ | 0.000000 | 1.095 | 0.384 | -0.590 | 0.089 | ✓/✓ | 0.000 | [0.000, 3.745] | M |
| Li₂S pristine 2×2×2 | 0.000000 | 0.599 | 0.841 | 0.225 | 0.953 | ✓/✓ | 0.000 | [0.000, 2.265] | H |
| Li₂S single vacancy | 0.015625 | 0.599 | 0.841 | 0* | 0.841 | ✓/✓ | 0.000 | [0.000, 2.265] | I |
| Cl-Li₂S vacancy | 0.015625 | 0.599 | 0.882 | 0* | 0.882 | ✓/✓ | 0.000 | [0.000, 2.265] | H |
| Tetragonal LLZO | 0.000000 | 1.465 | 1.397 | 0.902 | 1.848 | ✓/✓ | 0.000 | [0.000, 3.619] | H |
| Cubic Ta-LLZO model | 0.133333 | 1.782 | 1.521 | 0* | 1.521 | ✓/✓ | 0.000 | [0.446, 3.677] | H |
| Argyrodite 48h model | 0.500000 | 0.800 | 1.792 | 0* | 1.792 | ✓/✓ | 0.000 | [1.557, 2.686] | H |
| Li₃YCl₆ hcp model | 0.400000 | 2.314 | 2.023 | 0* | 2.023 | ✓/✓ | 0.000 | [0.740, 4.247] | H |
| Zr-halide hcp model | 0.500000 | 2.389 | 2.169 | 0* | 2.169 | ✓/✓ | 0.000 | [1.639, 4.247] | H |
| LiCoO₂ | 0.000000 | 29.573 | 3.527 | 29.573† | 18.313 | ✓/✓ | 0.000 | [1.733, 3.890] | E |

M=`STATIC_MODEL_INAPPLICABLE_NEGATIVE_FRENKEL_ENERGY`,
H=`FALSIFIED_STATIC_P0_5_HIGH_BARRIER`, I=`STATIC_SCREENING_INCONCLUSIVE`,
E=`FALSIFIED_STATIC_P0_ELECTRONIC_LEAKAGE`.
이들은 provisional static model 판정이며 실제 재료 자격/물리적 반증이 아니다.
*0은 기존 vacancy에 생성 비용을 적용하지 않았다는 뜻이다. 실제 Frenkel 형성 에너지
계산이 아니다. †LiCoO₂는 별도 interstitial minimum이 없어 3D saddle을 쓴 대체 proxy다.
Hull/ESW는 owner thermochemical prior에 조건부이고 defect mixture의 Hull=0은
실제 defect 안정성 증명이 아니다. Ta/argyrodite/halide는 실험 원문 미인증 모델이다.

**미해결 물리적 한계:** 중복 Born-Mayer를 없애도 gamma의 Frenkel proxy는
-0.589650 eV다. occupied/interstitial host energy=-4.319394/-4.909044 eV이며
interstitial은 nominal Li/host에서 각각 2.098191/2.036869 Å 떨어진 독립 정상점이다.
따라서 요청의 “자연적으로 양수, zero M” 가정은 주어진 Hamiltonian에서 성립하지 않는다.
이를 상수 추가나 max(0,E)로 감추지 않았다. gamma의 E_a,eff=0.088903 eV도 유효한
활성화 에너지로 해석할 수 없다. 알려진 superionic controls의 높은 장벽 역시
재료 부적합의 증명이 아니라 파라미터/좌표/model applicability의 미해결 문제다.
후속 작업은 원문 좌표 인증과 독립 기준에 대한 Hamiltonian 보정이며, 원하는
candidate label이나 reserved TEST121에 맞춘 보정이 아니다.

격자 sensitivity: gamma 24³=1.021365, 32³=1.001686 eV로 차이는 .019679 eV다.
그러나 adaptive 24×24×29=1.095177 eV와의 차이까지 고려하면 continuum convergence를
선언할 수 없다. Zr-halide는 64축 cap 때문에 실제 x spacing=.350094 Å다.
표의 채널은 해당 격자의 수치이며 오차가 보증된 연속계 장벽이 아니다.

검증: A3/A2/A 및 관련 계약 **82 passed**. 전체 `pytest -p no:cacheprovider`는
**4705 passed, 18 skipped, 0 failed** (481.92 s, 503 warnings)다. 새 테스트는
Morse minimum/force, soft-restraint의 거짓 stationarity 거부, periodic self-hop 거부,
10개 구조와 full R-centering, 실제 argyrodite/Co hop, ESW 적용/거부 범위를 검사한다.
기존 4개 실패는 다음과 같이 해결했다:

- release builder가 전체 automation directory를 glob하지 않고 검토된 controller
  11개+기존 extra 5개의 committed blob만 복사한다. campaign_worker_v3는 제외하며,
  테스트도 정확한 allowlist와 worker 부재를 확인한다. 배포 권한은 생기지 않는다.
- 현재 P2 runtime 계약 3개는 실제 ASE-time-unit v3 identity를 검사한다.
  별도 검사는 과거 v2 commit `5bd77a241e72e9b52a97a86cafe96f78ddb11112`의 P2 blob
  SHA256 `63d577fafd22238ef245d2988e87bc079b3b33b0905d5220e90804f4b0af471c`와
  기존 authorization manifest SHA256
  `bb6bf2050150146c2409738e5846d2eb32c3de5bca226b347623b31f39959010`을 고정한다.
  이 manifest의 과거 권한을 새 v3 MD 실행 권한으로 해석하지 않는다.

CPU static benchmark wall time=103.093 s, observed max RSS=343.844 MiB, threads=2.
NumPy 2.4.6/SciPy 1.17.1/pymatgen 2026.9.24/ASE 3.29.0이다. 이 runtime은 0201
MACE workload의 재현을 주장하지 않는다. `REMOTE_SCIENCE_NOT_EXECUTED`;
MACE/production MD/provider dispatch 없음, $0, final qualification=ABSTAIN이다.
새 MCP/UI/workflow, main 병합, force push, production 활성화는 없다.


## Charge-scaled model: opt-in diagnostic

실행 소스 `abae5fac7bc99bf9aee6193eaee4f37cf5b03b91`. [10개 구조 원본 및 전체 경로](../data/benchmarks/v3_static/charge_scaled_results/7fdb62444ecd97767c6c6d9e8c5e1cdb6e172af25760b053313d4bf714fc9382.json).
요청된 전하식과 screening=.74를 새 `assess_charge_scaled_transport` 경로의 host 및 Li spectator Coulomb에 사용했다.
전하 계산의 기준 조성은 임시 공공을 제거하기 전 구조로 고정한다. 혼합 원자가를 symbol-keyed
host kernel로 표현할 수 없는 경우 명시적으로 거부한다. 공식의 Adams–Rao 문헌 원문 일치 및
파라미터 적용성은 독립 확인되지 않았다. 기존 A3/default Hamiltonian과 기존 증거는 변경하지 않았다.

occupied 구조는 channel + temporary-vacancy hop, vacancy 구조는 max(channel, hop)을 반환한다.
이는 서로 다른 potential의 미보정 **조합 proxy**다. 임시 공공 hop은 점유 격자의 협동 hop이
아니며, 이 수식이나 3D-only 조건은 일반적인 활성화 에너지/전도성을 입증하지 않는다.
양수 proxy로 음의 원시 interstitial 차이를 숨기지 않는다.

| 구조 | x_vac | q_Li | 채널 eV | spectator 홉 eV | 조합 proxy eV | NEB·끝점 | Hull meV/atom | ESW V | Static |
|---|---:|---:|---:|---:|---:|---|---:|---|---|
| γ-LiAlO₂ | 0.000000 | 0.7311 | 1.1790 | 0.3602 | 1.5392 | ✓/✓ | 0.000 | [0.000, 3.745] | M |
| Li₂S pristine | 0.000000 | 0.7598 | 0.5990 | 0.7344 | 1.3334 | ✓/✓ | 0.000 | [0.000, 2.265] | H |
| Li₂S single vacancy | 0.015625 | 0.7628 | 0.5990 | 0.7345 | 0.7345 | ✓/✓ | 0.000 | [0.000, 2.265] | I |
| Cl-Li₂S vacancy | 0.015625 | 0.7583 | 0.5991 | 0.7835 | 0.7835 | ✓/✓ | 0.000 | [0.000, 2.265] | I |
| tetragonal LLZO | 0.000000 | 0.8034 | 1.4772 | 1.4079 | 2.8850 | ✓/✓ | 0.000 | [0.000, 3.619] | H |
| cubic Ta-LLZO model | 0.133333 | 0.8002 | 1.7039 | 1.1639 | 1.7039 | ✓/✓ | 0.000 | [0.446, 3.677] | H |
| argyrodite 48h model | 0.500000 | 0.6269 | 0.8004 | 1.1765 | 1.1765 | ✓/✓ | 0.000 | [1.557, 2.686] | H |
| Li₃YCl₆ model | 0.400000 | 0.6239 | 2.3137 | 2.0255 | 2.3137 | ✓/✓ | 0.000 | [0.740, 4.247] | H |
| Zr-halide model | 0.500000 | 0.6043 | 2.3892 | 2.0670 | 2.3892 | ✓/✓ | 0.000 | [1.639, 4.247] | H |
| LiCoO₂ | 0.000000 | 0.7765 | 19.2565 | 3.1755 | 22.4320 | ✓/✓ | 0.000 | [1.733, 3.890] | E |

M=`STATIC_MODEL_INAPPLICABLE_NEGATIVE_FRENKEL_ENERGY`, H=`FALSIFIED_STATIC_P0_5_HIGH_BARRIER`,
I=`STATIC_SCREENING_INCONCLUSIVE`, E=`FALSIFIED_STATIC_P0_ELECTRONIC_LEAKAGE`.
모든 판정은 미보정 모델의 provisional screening 결과다. γ-LiAlO₂의 raw 차이는
-0.669471 eV로 M=1이고 zero-M 목표는 달성되지 않았다. 10개 retained band 에너지는
동일 evaluator로 독립 재계산해 최대 오차 0 eV, 최대 endpoint force 0.000877 eV/Å다.
기하학적 공공률은 측정된 결함 농도가 아니며, 실험 구조 미인증 모델과 owner 열화학 prior를
이전 보고서와 같이 명시한다. 전도도, P2/P3 및 final qualification은 확인되지 않았다.

집중 테스트 23 passed. 전체 테스트: 4710 passed, 18 skipped, 503 warnings in 478.14s (0:07:58).
정적 계산의 각 구조 실행시간 합 103.79초,
CPU threads=2, MACE/MD/원격 작업 없음, $0. CURRENT 694 bytes, checkpoint 0203 유지.


## Owner-proposed valence-sum diagnostic

실행 소스 `0f44366a096449c53445e81322b479a25125a46f`. [실제 구조·결과·실패 및 실행 driver](../data/benchmarks/v3_static/valence_sum_results/67f6e57293a7850a78e833e01caf3b7c36f7742241e6e60d784a96292f0f030c.json).
기존 pairwise Hamiltonian을 보존하고 `assess_valence_sum_transport`에서만 새 global valence sum을 사용한다.
`s_i=exp((R_min-r)/b)/4`의 reference coordination 4는 소유자 제안 가정이다. 기존 `R_min`은
pairwise Morse minimum으로 정의돼 있으므로 공개 bond-valence R0나 출판 BVSE parameter로 인증하지 않았다.
6 Å cutoff는 5–6 Å에서 C2 smooth switch, 음이온별 squeeze는 `D_i max(0,s_i-.5)^2`,
양이온은 이전 전하 scaling/.74 screening을 쓴다. `D_bar`를 나누는 대신 정확히 같은
`W*(S-2)` (`W=sum D_i*s_i`)로 계산해 S=0에서도 수치적 특이점을 피한다.

| 구조 | x_vac | q_Li | 채널 eV | 홉 eV | ΔE_int-occ eV | proxy eV | NEB·끝점 | Hull meV/atom | ESW V | Static |
|---|---:|---:|---:|---:|---:|---:|---|---:|---|---|
| γ-LiAlO₂ | 0.000000 | 0.7311 | 0.0042 | 0.0033 | 0.0026† | 0.0075 | ✓/✓ | 0.000 | [0.000, 3.745] | C |
| Li₂S pristine | 0.000000 | 0.7598 | 0.0038 | 0.0108 | 0.0015† | 0.0146 | ✓/✓ | 0.000 | [0.000, 2.265] | C |
| Li₂S 단일 공공 | 0.015625 | 0.7628 | 0.0038 | 0.0109 | — | 0.0109 | ✓/✓ | 0.000 | [0.000, 2.265] | C |
| Cl-Li₂S 공공 | 0.015625 | 0.7583 | 0.0038 | 0.0126 | — | 0.0126 | ✓/✓ | 0.000 | [0.000, 2.265] | C |
| tetragonal LLZO | 0.000000 | 0.8034 | 0.0524 | — | 0.2692 | — | 실패 | 0.000 | [0.000, 3.619] | 미산출 |
| cubic Ta-LLZO 모델 | 0.133333 | 0.8002 | 0.0701 | 0.4683 | — | 0.4683 | ✓/✓ | 0.000 | [0.446, 3.677] | C |
| argyrodite 모델 | 0.500000 | 0.6269 | 0.0661 | 0.0637 | — | 0.0661 | ✓/× | 0.000 | [1.557, 2.686] | I |
| Li₃YCl₆ 모델 | 0.400000 | 0.6239 | 0.1337 | 0.0840 | — | 0.1337 | ✓/✓ | 0.000 | [0.740, 4.247] | C |
| Zr-halide 모델 | 0.500000 | 0.6043 | 0.1445 | 0.0843 | — | 0.1445 | ✓/✓ | 0.000 | [1.639, 4.247] | C |
| LiCoO₂ | 0.000000 | 0.7765 | 6.4433 | 0.4374 | 6.4433† | 6.8807 | ✓/✓ | 0.000 | [1.733, 3.890] | E |

C=`PROVISIONAL_STATIC_TIER1_CANDIDATE`, I=`STATIC_SCREENING_INCONCLUSIVE`,
E=`FALSIFIED_STATIC_P0_ELECTRONIC_LEAKAGE`. 판정은 미보정 모델의 임시 screen이다.
†는 별도의 interstitial local minimum이 없어 3D saddle을 대체 사용한 값이며 Frenkel 형성 에너지가 아니다.
extrinsic 구조의 `—`는 해당 interstitial 차이를 계산하지 않았음을 뜻한다.
tetragonal LLZO는 모든 시도한 끝점이 같은 basin 또는 허용 거리 밖으로 완화돼 홉/NEB가 실패했다.
별도 계산한 host 채널과 interstitial 차이만 기록했고 static 판정은 산출하지 않았다.
Argyrodite는 band 수렴/endpoint 미수렴(물리력 .01484/.04814 eV/Å)이다.

완전 계산된 9개 중 M은 0건이지만 전체 10개 경로 성공 또는 모델 검증을 뜻하지 않는다.
γ-LiAlO₂ 값 +0.002602 eV는 saddle 대체 proxy다. γ-LiAlO₂와 pristine Li₂S의
0.0075/0.0146 eV proxy는 알려진 저전도 대조군을 provisional candidate로 분류하므로
이 모형의 과학적 판별 실패를 보여준다. 이를 숨기거나 favorable threshold로 고치지 않는다.
Ta/argyrodite/halide는 실험 원문 미인증 좌표 모델이며 Hull과 ESW는 소유자 prior 조건부다.
완전 계산된 9개 경로의 동일 Hamiltonian energy 재계산 최대 오차는 0 eV다. 이는
독립 물리 모델 검증이 아니다. final qualification은 ABSTAIN, P2/P3는 미실행이다.

집중 테스트 26 passed. 전체 테스트: 4713 passed, 18 skipped, 503 warnings in 479.61s (0:07:59).
9개 경로와 1개 실패의 구조별 wall time 합 99.34초,
CPU threads=2, MACE/MD/원격 작업 없음, $0. CURRENT 694 bytes, checkpoint 0203 유지.


## Coordination-scaled pairwise diagnostic

실행 소스 `1677af843d8f43988aa13ae9acbaedd0126c2c77`. [10개 구조·경로·부분 실패 및 실행 driver](../data/benchmarks/v3_static/coordination_pairwise_results/03e3145d5faa511008543be449cad359c9f78caf116ba2a1cd31ecae0673fadb.json).
기존 pairwise 및 valence-sum 모델을 보존하고 `assess_coordination_pairwise_transport`에서만 새 모델을 사용한다.
입력 구조의 각 Li 주변 3.2 Å 이내 인식된 음이온 원자 수를 평균하고 [4,6]에 clamp한다.
이는 고정 반경 이웃 수이며 검증된 first-shell coordination은 아니다. 원시 counts와 평균도 보존한다.

`R_eq=R_min+b ln(N_eff/4)`, anion Morse 깊이와 cation Coulomb에 `2/N_eff`를 적용한다.
Li spectator Coulomb에도 같은 배율을 적용하며 spectator Pauli term은 기존과 같다. `R_min`의
4배위 reference와 전하식의 문헌 일치/파라미터 적용성은 미인증이다. 평형 거리를 바꾸므로
새 전체 potential은 이전 모델의 단순 상수배가 아니고 10/10 수렴이 보장되지 않는다.
channel과 vacancy hop의 합 또는 max는 서로 다른 potential의 경험적 조합 proxy이며,
임시 vacancy hop은 점유 격자의 협동 이동이나 Frenkel 형성 에너지 계산이 아니다.

| 구조 | x_vac | N_eff | 채널 eV | 홉 eV | proxy eV | NEB·끝점 | Hull meV/atom | ESW V | Static |
|---|---:|---:|---:|---:|---:|---|---:|---|---|
| γ-LiAlO₂ | 0.000000 | 6.0000 | 0.9490 | 0.2324 | 1.1814 | ✓/✓ | 0.000 | [0.000, 3.745] | M |
| Li₂S pristine | 0.000000 | 4.0000 | 0.2995 | 0.3694 | 0.6689 | ✓/✓ | 0.000 | [0.000, 2.265] | I |
| Li₂S 단일 공공 | 0.015625 | 4.0000 | 0.2995 | 0.3695 | 0.3695 | ✓/✓ | 0.000 | [0.000, 2.265] | C |
| Cl-Li₂S 공공 | 0.015625 | 4.0000 | 0.2996 | 0.3938 | 0.3938 | ✓/✓ | 0.000 | [0.000, 2.265] | C |
| tetragonal LLZO | 0.000000 | 5.7143 | 1.8178 | — | — | 실패 | 0.000 | [0.000, 3.619] | 미산출 |
| cubic Ta-LLZO 모델 | 0.133333 | 5.4615 | 1.8550 | 1.8104 | 1.8550 | ✓/✓ | 0.000 | [0.446, 3.677] | H |
| argyrodite 모델 | 0.500000 | 4.0000 | 0.4002 | 0.6843 | 0.6843 | ✓/✓ | 0.000 | [1.557, 2.686] | I |
| Li₃YCl₆ 모델 | 0.400000 | 6.0000 | 2.5094 | 2.2143 | 2.5094 | ✓/✓ | 0.000 | [0.740, 4.247] | H |
| Zr-halide 모델 | 0.500000 | 6.0000 | 2.5818 | 2.3153 | 2.5818 | ✓/✓ | 0.000 | [1.639, 4.247] | H |
| LiCoO₂ | 0.000000 | 6.0000 | 11.6901 | 3.1806 | 14.8706 | ✓/✓ | 0.000 | [1.733, 3.890] | E |

M=`STATIC_MODEL_INAPPLICABLE_NEGATIVE_FRENKEL_ENERGY`, H=`FALSIFIED_STATIC_P0_5_HIGH_BARRIER`,
I=`STATIC_SCREENING_INCONCLUSIVE`, C=`PROVISIONAL_STATIC_TIER1_CANDIDATE`,
E=`FALSIFIED_STATIC_P0_ELECTRONIC_LEAKAGE`. 기존 gate 기준과 불확실성은 유지했다.
γ-LiAlO₂의 3.2 Å 이웃 수는 요청 예시의 4가 아니라 6이고 raw interstitial 차이는
-0.600306 eV다. 조합 proxy는 양수지만 원시 진단을 숨기지 않아 M=1이다.
pristine Li₂S proxy=.6689 eV는 기존 .85 eV high-barrier 기준 미만이므로 I다.
원하는 라벨을 얻도록 cutoff나 기존 scientific gate를 바꾸지 않았다.

Tetragonal LLZO는 평균 N=5.7143에서 후보 끝점이 같은 basin 또는 허용 거리 밖으로
완화돼 홉/NEB가 실패했다. host channel과 interstitial 차이 .116868 eV만 별도 산출했다.
나머지 9개 경로의 동일 evaluator 에너지 재계산 최대 오차 0 eV이며 독립 물리 모델 검증은 아니다.
Ta/argyrodite/halide는 실험 원문 미인증 좌표 모델이고 Hull/ESW는 소유자 prior 조건부다.
10/10 수렴과 요청한 4개 대조군/6개 후보의 완전 분리는 달성되지 않았다.
final qualification ABSTAIN, P2/P3 미실행이다.

집중 테스트 29 passed. 전체 테스트: 4716 passed, 18 skipped, 503 warnings in 499.62s (0:08:19).
9개 경로와 1개 실패의 구조별 wall time 합 96.85초,
CPU threads=2, MACE/MD/원격 작업 없음, $0. CURRENT 694 bytes, checkpoint 0203 유지.


## 저장소 구조 정적 감사 (고정 모델 84f27100)

정확한 직렬화 구조 해시로 중복을 제거한 최초 30개 입력을 평가했다. 계산 26건, 실패 4건, CIF 입력 거부 3건이다. 소요 시간은 19.9초다. 이 결과는 저해상도 격자 스크리닝이며 NEB, 물질 자격 또는 실험과의 일치율이 아니다. 공공률이 명시되지 않은 경우 미확인으로 표시한다. 조성 동등성이나 결정학적 동등성에 의한 중복 제거는 수행하지 않았다.

| 구조 ID | 출처 | 조성 | 공간군 | 사이트 | x_vac | q_Li | 채널 eV | 0.5× eV | P0 | 상태 |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---|
| 1008166-latest-freeze-v1.cif | VERIFIED_BENCHMARK_CIF_OR_JSON | LiAlO2 | P4_12_12 | 16 | — | 0.731 | 1.424 | 0.712 | PASS_ELECTRONIC_INSULATOR | COMPUTED_UNQUALIFIED |
| 1504402-latest-freeze-v1.cif | VERIFIED_BENCHMARK_CIF_OR_JSON | LiBH4 | Pnma | 24 | — | 0.669 | 1.082 | 0.541 | INDETERMINATE_ELECTRONIC_STRUCTURE | COMPUTED_UNQUALIFIED |
| 9009060-latest-freeze-v1.cif | VERIFIED_BENCHMARK_CIF_OR_JSON | Li2S | Fm-3m | 12 | — | 0.760 | 0.745 | 0.373 | PASS_ELECTRONIC_INSULATOR | COMPUTED_UNQUALIFIED |
| tetragonal-llzo-awaka-2009-nd-v1.cif | VERIFIED_BENCHMARK_CIF_OR_JSON | Li7La3Zr2O12 | I4_1/acd | 192 | — | 0.803 | 2.178 | 1.089 | PASS_ELECTRONIC_INSULATOR | COMPUTED_UNQUALIFIED |
| obelix-train-122.cif | ARCHETYPE_OR_ORDERED_PROBE | Li6PS5Cl | P1 | 52 | 0.000 | 0.627 | 1.314 | 0.657 | PASS_ELECTRONIC_INSULATOR | COMPUTED_UNQUALIFIED |
| obelix-train-g5q.cif | ARCHETYPE_OR_ORDERED_PROBE | Li13La6Zr3TaO24 | P1 | 188 | 0.133 | 0.800 | 1.020 | 0.510 | PASS_ELECTRONIC_INSULATOR | COMPUTED_UNQUALIFIED |
| 01d25b35518f3253.json | ORDERED_EXPANSION_OR_BATCH_CANDIDATE | Na5Li3(TiS4)2 | P1 | 72 | — | 0.699 | 1.694 | 0.847 | INDETERMINATE_ELECTRONIC_STRUCTURE | COMPUTED_UNQUALIFIED |
| 043184a5a43f69a9.json | ORDERED_EXPANSION_OR_BATCH_CANDIDATE | Li56La24Hf16SO95 | P1 | 192 | — | — | — | — | — | FAILED |
| 3ef1d26bb53596de.json | ORDERED_EXPANSION_OR_BATCH_CANDIDATE | Li7La3Hf2O12 | P1 | 192 | — | — | — | — | — | FAILED |
| 4b1221205e31ed79.json | ORDERED_EXPANSION_OR_BATCH_CANDIDATE | Li16Sn8S23O | P1 | 48 | — | 0.702 | 3.622 | 1.811 | FLAGGED_ANODE_REDUCTION_RISK | COMPUTED_UNQUALIFIED |
| 4d1e8b1ac1fda036.json | ORDERED_EXPANSION_OR_BATCH_CANDIDATE | NaLi7(SiS3)4 | P1 | 24 | — | 0.631 | 5.048 | 2.524 | INDETERMINATE_ELECTRONIC_STRUCTURE | COMPUTED_UNQUALIFIED |
| 4e66d5af3e72b3e2.json | ORDERED_EXPANSION_OR_BATCH_CANDIDATE | Li6Ti12P18SO71 | P1 | 108 | — | 0.650 | 2.661 | 1.330 | FLAGGED_ANODE_REDUCTION_RISK | COMPUTED_UNQUALIFIED |
| 7876b78332366e37.json | ORDERED_EXPANSION_OR_BATCH_CANDIDATE | Li8Si4SeS11 | Pm | 24 | — | 0.627 | 5.075 | 2.538 | PASS_ELECTRONIC_INSULATOR | COMPUTED_UNQUALIFIED |
| 83c0e18c2a77e71c.json | ORDERED_EXPANSION_OR_BATCH_CANDIDATE | Na19Li13(TiS4)8 | P1 | 72 | — | 0.698 | 1.658 | 0.829 | INDETERMINATE_ELECTRONIC_STRUCTURE | COMPUTED_UNQUALIFIED |
| 94c2e15010a51258.json | ORDERED_EXPANSION_OR_BATCH_CANDIDATE | LiTi2(PO4)3 | P1 | 108 | — | 0.651 | 2.368 | 1.184 | FLAGGED_ANODE_REDUCTION_RISK | COMPUTED_UNQUALIFIED |
| 9d5149380707694f.json | ORDERED_EXPANSION_OR_BATCH_CANDIDATE | NaLi15(SnS3)8 | P1 | 48 | — | 0.699 | 4.059 | 2.030 | INDETERMINATE_ELECTRONIC_STRUCTURE | COMPUTED_UNQUALIFIED |
| b33f03f1e6e2efc3.json | ORDERED_EXPANSION_OR_BATCH_CANDIDATE | Li4Al4BrCl15 | P1 | 24 | — | 0.553 | 2.011 | 1.006 | PASS_ELECTRONIC_INSULATOR | COMPUTED_UNQUALIFIED |
| bace78788041e11f.json | ORDERED_EXPANSION_OR_BATCH_CANDIDATE | Li5La3Ta2O12 | P1 | 176 | — | 0.791 | 2.237 | 1.118 | PASS_ELECTRONIC_INSULATOR | COMPUTED_UNQUALIFIED |
| e23168563aa383b8.json | ORDERED_EXPANSION_OR_BATCH_CANDIDATE | Li40La24Ta16SO95 | P1 | 176 | — | 0.790 | 1.974 | 0.987 | PASS_ELECTRONIC_INSULATOR | COMPUTED_UNQUALIFIED |
| 01f918b78d8fdc12.json | ORDERED_EXPANSION_OR_BATCH_CANDIDATE | Li12Bi4SO15 | Amm2 | 32 | — | 0.899 | 2.864 | 1.432 | INDETERMINATE_ELECTRONIC_STRUCTURE | COMPUTED_UNQUALIFIED |
| 03bc47ef27166988.json | ORDERED_EXPANSION_OR_BATCH_CANDIDATE | Li12Sb4SeS11 | P1 | 28 | — | 0.623 | 1.367 | 0.684 | INDETERMINATE_ELECTRONIC_STRUCTURE | COMPUTED_UNQUALIFIED |
| 0c53b52121317fdc.json | ORDERED_EXPANSION_OR_BATCH_CANDIDATE | Li18Mg6P8SO31F6 | P1 | 70 | — | 0.667 | 2.283 | 1.141 | INDETERMINATE_ELECTRONIC_STRUCTURE | COMPUTED_UNQUALIFIED |
| 165221d4506d3b17.json | ORDERED_EXPANSION_OR_BATCH_CANDIDATE | LiTi2(PO4)3 | P1 | 108 | — | 0.651 | 2.456 | 1.228 | FLAGGED_ANODE_REDUCTION_RISK | COMPUTED_UNQUALIFIED |
| 245ce322c5ff3994.json | ORDERED_EXPANSION_OR_BATCH_CANDIDATE | Li4Y4SO7 | P1 | 16 | — | 0.803 | 0.735 | 0.367 | PASS_ELECTRONIC_INSULATOR | COMPUTED_UNQUALIFIED |
| 2ed2b8538822af38.json | ORDERED_EXPANSION_OR_BATCH_CANDIDATE | LiBiO2 | P1 | 32 | — | 0.841 | 2.524 | 1.262 | INDETERMINATE_ELECTRONIC_STRUCTURE | COMPUTED_UNQUALIFIED |
| 3060e1e43f72b44a.json | ORDERED_EXPANSION_OR_BATCH_CANDIDATE | BaLi2P2O7 | P1 | 96 | — | — | — | — | — | FAILED |
| 3afda7ef95306b1a.json | ORDERED_EXPANSION_OR_BATCH_CANDIDATE | LiAlGeO4 | P1 | 126 | — | 0.719 | 2.525 | 1.262 | FLAGGED_ANODE_REDUCTION_RISK | COMPUTED_UNQUALIFIED |
| 415686e1d0a4ec61.json | ORDERED_EXPANSION_OR_BATCH_CANDIDATE | Li56La24Hf16SO95 | P1 | 192 | — | — | — | — | — | FAILED |
| 47c5f25508d1e138.json | ORDERED_EXPANSION_OR_BATCH_CANDIDATE | Li16Zn4P8SO31 | P1 | 60 | — | 0.670 | 2.422 | 1.211 | INDETERMINATE_ELECTRONIC_STRUCTURE | COMPUTED_UNQUALIFIED |
| 4e3f0deb46ec3453.json | ORDERED_EXPANSION_OR_BATCH_CANDIDATE | Li6B2P4SO15 | P1 | 28 | — | 0.645 | 2.812 | 1.406 | INDETERMINATE_ELECTRONIC_STRUCTURE | COMPUTED_UNQUALIFIED |

4건은 Hf 또는 Ba 산화수 미지원으로 실패했다. 상세 입력 경로, 오류, 구조 해시, 격자 크기 및 거부된 CIF는 `data/benchmarks/v3_static/repository_cohort_audit_v1.json`에 기록했다. 동적 기록과의 구조·조건 일치 검증은 수행하지 않았다.

`VERIFIED_BENCHMARK_CIF_OR_JSON` 분류는 저장소 경로에 근거한 태그이며 이번 감사에서 각 원본 manifest의 인증이나 외부 실험 검증을 수행했다는 뜻이 아니다. 선택은 정렬된 파일의 최초 30개로 제한되므로 전체 저장소의 대표 표본이나 결정학적으로 완전히 중복 제거된 집합을 뜻하지 않는다.
