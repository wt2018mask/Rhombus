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
